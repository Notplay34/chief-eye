from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models import EmployeeRole


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: str
    telegram_id: Optional[int] = None
    login: Optional[str] = None
    is_active: bool

class EmployeeCreate(BaseModel):
    name: str
    role: EmployeeRole
    login: Optional[str] = None
    password: Optional[str] = None
    telegram_id: Optional[int] = None


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[EmployeeRole] = None
    login: Optional[str] = None
    password: Optional[str] = None
    telegram_id: Optional[int] = None
    is_active: Optional[bool] = None
