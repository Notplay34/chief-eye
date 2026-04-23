"""Order access helpers shared by orders/documents routes."""

from typing import Optional

from sqlalchemy import Select

from app.api.auth import UserInfo
from app.models import Order
from app.models.employee import EmployeeRole
from app.services.errors import ServiceError
from app.services.template_registry import PLATE_DOCUMENT_TEMPLATES


def _role(user: UserInfo) -> EmployeeRole:
    return EmployeeRole(user.role)


def can_access_order(user: UserInfo, order: Order) -> bool:
    role = _role(user)
    if role in (EmployeeRole.ROLE_ADMIN, EmployeeRole.ROLE_MANAGER, EmployeeRole.ROLE_OPERATOR):
        return True
    if role == EmployeeRole.ROLE_PLATE_OPERATOR:
        return bool(order.need_plate)
    return False


def ensure_can_access_order(user: UserInfo, order: Order) -> None:
    if not can_access_order(user, order):
        raise ServiceError("Нет доступа к этому заказу", status_code=403)


def ensure_can_access_plate_workflow(user: UserInfo, order: Order) -> None:
    ensure_can_access_order(user, order)
    if not order.need_plate:
        raise ServiceError("Заказ не относится к потоку номеров", status_code=403)


def ensure_can_print_template(user: UserInfo, order: Order, template_name: str) -> None:
    ensure_can_access_order(user, order)
    role = _role(user)
    if role in (EmployeeRole.ROLE_ADMIN, EmployeeRole.ROLE_MANAGER):
        return
    if role == EmployeeRole.ROLE_OPERATOR and template_name not in PLATE_DOCUMENT_TEMPLATES:
        return
    if role == EmployeeRole.ROLE_PLATE_OPERATOR and template_name in PLATE_DOCUMENT_TEMPLATES:
        return
    raise ServiceError("Нет доступа к этому документу", status_code=403)


def apply_orders_scope(query: Select, user: UserInfo, pavilion: Optional[int] = None) -> Select:
    role = _role(user)
    if role == EmployeeRole.ROLE_PLATE_OPERATOR:
        if pavilion == 1:
            raise ServiceError("Нет доступа к заказам павильона 1", status_code=403)
        return query.where(Order.need_plate == True)
    if role == EmployeeRole.ROLE_OPERATOR and pavilion == 2:
        raise ServiceError("Нет доступа к заказам павильона 2", status_code=403)
    return query
