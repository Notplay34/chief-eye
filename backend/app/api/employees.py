from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import RequireAdmin, RequireFormAccess, UserInfo
from app.core.database import get_db
from app.models import Employee
from app.models.employee import EmployeeRole
from app.schemas.employee import EmployeeCreate, EmployeeResponse, EmployeeUpdate
from app.services.auth_service import hash_password

router = APIRouter(prefix="/employees", tags=["employees"])


def _emp_to_response(e: Employee) -> EmployeeResponse:
    return EmployeeResponse(
        id=e.id,
        name=e.name,
        role=e.role.value,
        telegram_id=e.telegram_id,
        login=e.login,
        is_active=e.is_active,
    )


@router.get("", response_model=list[EmployeeResponse])
async def list_employees(
    all_employees: bool = Query(False, alias="all", description="Только для админа: показать всех"),
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(RequireFormAccess),
):
    if all_employees and current_user.role == EmployeeRole.ROLE_ADMIN.value:
        result = await db.execute(select(Employee).order_by(Employee.id))
    else:
        result = await db.execute(
            select(Employee).where(Employee.is_active == True).order_by(Employee.id)
        )
    employees = result.scalars().all()
    return [_emp_to_response(e) for e in employees]


@router.post("", response_model=EmployeeResponse)
async def create_employee(
    data: EmployeeCreate,
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequireAdmin),
):
    if data.login:
        r = await db.execute(select(Employee.id).where(Employee.login == data.login.strip()))
        if r.scalar_one_or_none() is not None:
            raise HTTPException(status_code=400, detail="Логин уже занят")
    emp = Employee(
        name=data.name,
        role=data.role,
        telegram_id=data.telegram_id,
        login=data.login,
        password_hash=hash_password(data.password) if data.password else None,
        is_active=True,
    )
    db.add(emp)
    await db.flush()
    await db.refresh(emp)
    return _emp_to_response(emp)


@router.patch("/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    _user: UserInfo = Depends(RequireAdmin),
):
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    if data.name is not None:
        emp.name = data.name
    if data.role is not None:
        emp.role = data.role
    if data.telegram_id is not None:
        emp.telegram_id = data.telegram_id
    if data.login is not None:
        emp.login = data.login if data.login.strip() else None
    if data.password is not None and data.password.strip():
        emp.password_hash = hash_password(data.password)
    if data.is_active is not None:
        emp.is_active = data.is_active
    await db.commit()
    await db.refresh(emp)
    return _emp_to_response(emp)


@router.delete("/{employee_id}", response_model=EmployeeResponse)
async def deactivate_employee(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserInfo = Depends(RequireAdmin),
):
    """Деактивировать сотрудника (мягкое удаление — is_active=false)."""
    if employee_id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя деактивировать себя")
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    emp.is_active = False
    await db.commit()
    await db.refresh(emp)
    return _emp_to_response(emp)
