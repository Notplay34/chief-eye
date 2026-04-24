"""Веб-авторизация: логин по login+пароль, JWT, проверка ролей."""
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.identity import normalize_login
from app.core.logging_config import get_logger
from app.core.permissions import allowed_pavilions, get_menu_items
from app.models import Employee
from app.models.employee import EmployeeRole
from app.services.auth_service import (
    create_access_token,
    decode_token,
    verify_password,
)
from app.services.audit_service import write_audit_log

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)
logger = get_logger(__name__)

MIN_PASSWORD_LENGTH = 8
LOGIN_RATE_WINDOW_SECONDS = 15 * 60
LOGIN_RATE_MAX_FAILURES = 5
LOGIN_RATE_LOCK_SECONDS = 5 * 60
_login_failures: dict[str, list[float]] = {}


class UserInfo(BaseModel):
    id: int
    name: str
    role: str
    login: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[UserInfo]:
    has_header = credentials is not None and credentials.scheme.lower() == "bearer"
    if not has_header:
        logger.warning("auth/me: заголовок Authorization отсутствует или не Bearer")
        return None
    payload = decode_token(credentials.credentials)
    if not payload or "sub" not in payload:
        logger.warning("auth/me: токен не прошёл проверку (неверный или истёк)")
        return None
    sub = payload["sub"]
    try:
        employee_id = int(sub)
    except (TypeError, ValueError):
        logger.warning("auth/me: некорректный subject в токене")
        return None

    result = await db.execute(
        select(Employee).where(Employee.id == employee_id, Employee.is_active == True)
    )
    emp = result.scalar_one_or_none()
    if not emp:
        logger.warning("auth/me: пользователь из токена не найден или деактивирован")
        return None

    return UserInfo(
        id=emp.id,
        name=emp.name,
        role=emp.role.value,
        login=emp.login or "",
    )


def require_roles(allowed_roles: List[EmployeeRole]):
    async def _check(
        current_user: Optional[UserInfo] = Depends(get_current_user),
    ) -> UserInfo:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Требуется авторизация",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            role_enum = EmployeeRole(current_user.role)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Неизвестная роль")
        if role_enum not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
        return current_user
    return _check


RequireAnyAuth = require_roles([
    EmployeeRole.ROLE_OPERATOR,
    EmployeeRole.ROLE_MANAGER,
    EmployeeRole.ROLE_ADMIN,
    EmployeeRole.ROLE_PLATE_OPERATOR,
])
RequireFormAccess = require_roles([EmployeeRole.ROLE_OPERATOR, EmployeeRole.ROLE_MANAGER, EmployeeRole.ROLE_ADMIN])
RequireOrdersListAccess = require_roles([EmployeeRole.ROLE_OPERATOR, EmployeeRole.ROLE_MANAGER, EmployeeRole.ROLE_ADMIN, EmployeeRole.ROLE_PLATE_OPERATOR])
RequireAnalyticsAccess = require_roles([EmployeeRole.ROLE_ADMIN])
RequirePlateAccess = require_roles([EmployeeRole.ROLE_PLATE_OPERATOR, EmployeeRole.ROLE_MANAGER, EmployeeRole.ROLE_ADMIN])
RequireCashAccess = require_roles([EmployeeRole.ROLE_OPERATOR, EmployeeRole.ROLE_PLATE_OPERATOR, EmployeeRole.ROLE_MANAGER, EmployeeRole.ROLE_ADMIN])
RequireAdmin = require_roles([EmployeeRole.ROLE_ADMIN])


@router.post("/login", response_model=LoginResponse)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    username = normalize_login(form.username)
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    now = time.monotonic()
    failures = [
        timestamp
        for timestamp in _login_failures.get(username, [])
        if now - timestamp < LOGIN_RATE_WINDOW_SECONDS
    ]
    _login_failures[username] = failures
    if len(failures) >= LOGIN_RATE_MAX_FAILURES and now - failures[-1] < LOGIN_RATE_LOCK_SECONDS:
        await write_audit_log(
            db,
            user=None,
            event_type="login_rate_limited",
            entity_type="auth",
            entity_id=None,
            payload={"login": username},
        )
        raise HTTPException(status_code=429, detail="Слишком много попыток входа. Повторите позже.")

    result = await db.execute(
        select(Employee).where(
            Employee.login_normalized == username,
            Employee.is_active == True,
        )
    )
    emp = result.scalar_one_or_none()
    if not emp or not emp.password_hash:
        failures.append(now)
        _login_failures[username] = failures
        await write_audit_log(
            db,
            user=None,
            event_type="login_failed",
            entity_type="auth",
            entity_id=None,
            payload={"login": username, "reason": "user_not_found_or_inactive"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )
    if not verify_password(form.password, emp.password_hash):
        failures.append(now)
        _login_failures[username] = failures
        await write_audit_log(
            db,
            user=None,
            event_type="login_failed",
            entity_type="auth",
            entity_id=emp.id,
            payload={"login": username, "reason": "bad_password"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )
    _login_failures.pop(username, None)
    token = create_access_token(
        subject=emp.id,
        role=emp.role.value,
        name=emp.name,
        login=emp.login or "",
    )
    return LoginResponse(
        access_token=token,
        user=UserInfo(id=emp.id, name=emp.name, role=emp.role.value, login=emp.login or ""),
    )


class MenuItem(BaseModel):
    id: str
    label: str
    href: str
    divider: Optional[bool] = None
    action: Optional[str] = None
    group: Optional[str] = None


class MeResponse(BaseModel):
    id: int
    name: str
    role: str
    login: str
    allowed_pavilions: List[int]
    menu_items: List[MenuItem]


@router.get("/me", response_model=MeResponse)
async def me(current_user: UserInfo = Depends(RequireAnyAuth)):
    """Текущий пользователь, разрешённые павильоны и пункты меню по роли."""
    pavilions = allowed_pavilions(current_user.role)
    menu = get_menu_items(current_user.role)
    return MeResponse(
        id=current_user.id,
        name=current_user.name,
        role=current_user.role,
        login=current_user.login,
        allowed_pavilions=pavilions,
        menu_items=[
            MenuItem(
                id=m.get("id", ""),
                label=m.get("label", ""),
                href=m.get("href", "#"),
                divider=m.get("divider"),
                action=m.get("action"),
                group=m.get("group"),
            )
            for m in menu
        ],
    )


class ChangePasswordBody(BaseModel):
    old_password: str
    new_password: str


@router.post("/change-password")
async def change_password(
    body: ChangePasswordBody,
    current_user: UserInfo = Depends(RequireAnyAuth),
    db: AsyncSession = Depends(get_db),
):
    """Смена пароля текущего пользователя (требуется старый пароль)."""
    from app.services.auth_service import hash_password
    if not body.new_password or len(body.new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"Новый пароль должен быть не менее {MIN_PASSWORD_LENGTH} символов")
    result = await db.execute(select(Employee).where(Employee.id == current_user.id))
    emp = result.scalar_one_or_none()
    if not emp or not emp.password_hash:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if not verify_password(body.old_password, emp.password_hash):
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")
    emp.password_hash = hash_password(body.new_password)
    db.add(emp)
    await db.flush()
    await write_audit_log(
        db,
        user=current_user,
        event_type="password_changed",
        entity_type="employee",
        entity_id=emp.id,
        payload={"login": emp.login},
    )
    return {"ok": True}
