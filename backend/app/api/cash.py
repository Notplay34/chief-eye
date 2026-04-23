"""API касс и смен: открытие/закрытие смены по павильонам; касса номеров (plate-rows)."""
from decimal import Decimal
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.api.auth import RequireCashAccess, RequirePlateAccess, UserInfo
from app.models import CashShift, ShiftStatus, Payment, CashRow, PlateCashRow, PlatePayout
from app.models.employee import EmployeeRole
from app.schemas.cash import (
    ShiftOpen, ShiftClose, ShiftResponse, ShiftCurrentResponse,
    CashRowCreate, CashRowUpdate, CashRowResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/cash", tags=["cash"])


def _shift_to_response(shift: CashShift) -> dict:
    return {
        "id": shift.id,
        "pavilion": shift.pavilion,
        "opened_by_id": shift.opened_by_id,
        "opened_at": shift.opened_at.isoformat() if shift.opened_at else "",
        "closed_at": shift.closed_at.isoformat() if shift.closed_at else None,
        "closed_by_id": shift.closed_by_id,
        "opening_balance": float(shift.opening_balance),
        "closing_balance": float(shift.closing_balance) if shift.closing_balance is not None else None,
        "status": shift.status.value,
    }


async def _get_current_shift(db: AsyncSession, pavilion: int) -> Optional[CashShift]:
    q = select(CashShift).where(
        CashShift.pavilion == pavilion,
        CashShift.status == ShiftStatus.OPEN,
    ).order_by(CashShift.opened_at.desc()).limit(1)
    r = await db.execute(q)
    return r.scalar_one_or_none()


def _can_manage_pavilion(user: UserInfo, pavilion: int) -> bool:
    try:
        role = EmployeeRole(user.role)
    except ValueError:
        return False
    if pavilion == 1:
        return role in (EmployeeRole.ROLE_OPERATOR, EmployeeRole.ROLE_MANAGER, EmployeeRole.ROLE_ADMIN)
    return role in (EmployeeRole.ROLE_PLATE_OPERATOR, EmployeeRole.ROLE_MANAGER, EmployeeRole.ROLE_ADMIN)


@router.post("/shifts", response_model=dict)
async def open_shift(
    body: ShiftOpen,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Открыть смену по павильону. Павильон 1 — оператор/менеджер/админ, павильон 2 — оператор изготовления/менеджер/админ."""
    if not _can_manage_pavilion(user, body.pavilion):
        raise HTTPException(status_code=403, detail="Нет доступа к кассе этого павильона")
    current = await _get_current_shift(db, body.pavilion)
    if current:
        raise HTTPException(
            status_code=400,
            detail=f"Смена павильона {body.pavilion} уже открыта (id={current.id}). Сначала закройте её.",
        )
    shift = CashShift(
        pavilion=body.pavilion,
        opened_by_id=user.id,
        opening_balance=body.opening_balance,
        status=ShiftStatus.OPEN,
    )
    db.add(shift)
    await db.flush()
    logger.info("Открыта смена id=%s павильон=%s", shift.id, body.pavilion)
    return {"id": shift.id, "pavilion": shift.pavilion, "opened_at": shift.opened_at.isoformat(), "status": "OPEN"}


@router.get("/shifts/current")
async def get_current_shift(
    pavilion: int = Query(..., ge=1, le=2),
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Текущая открытая смена по павильону и сумма по ней."""
    if not _can_manage_pavilion(user, pavilion):
        raise HTTPException(status_code=403, detail="Нет доступа к кассе этого павильона")
    shift = await _get_current_shift(db, pavilion)
    if not shift:
        return {"shift": None, "total_in_shift": 0}
    q = select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.shift_id == shift.id)
    r = await db.execute(q)
    total = r.scalar_one() or Decimal("0")
    return {
        "shift": _shift_to_response(shift),
        "total_in_shift": float(total),
    }


@router.get("/shifts", response_model=list)
async def list_shifts(
    pavilion: Optional[int] = Query(None, ge=1, le=2),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Список смен (фильтр по павильону и статусу)."""
    q = select(CashShift).order_by(CashShift.opened_at.desc()).limit(limit)
    if pavilion is not None:
        q = q.where(CashShift.pavilion == pavilion)
    if status is not None:
        try:
            q = q.where(CashShift.status == ShiftStatus(status))
        except ValueError:
            pass
    r = await db.execute(q)
    shifts = r.scalars().all()
    return [_shift_to_response(s) for s in shifts]


@router.patch("/shifts/{shift_id}/close", response_model=dict)
async def close_shift(
  shift_id: int,
  body: ShiftClose,
  db: AsyncSession = Depends(get_db),
  user: UserInfo = Depends(RequireCashAccess),
):
    """Закрыть смену (указать посчитанную наличность)."""
    r = await db.execute(select(CashShift).where(CashShift.id == shift_id))
    shift = r.scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=404, detail="Смена не найдена")
    if shift.status != ShiftStatus.OPEN:
        raise HTTPException(status_code=400, detail="Смена уже закрыта")
    if not _can_manage_pavilion(user, shift.pavilion):
        raise HTTPException(status_code=403, detail="Нет доступа к кассе этого павильона")
    from datetime import datetime
    shift.closed_at = datetime.utcnow()
    shift.closed_by_id = user.id
    shift.closing_balance = body.closing_balance
    shift.status = ShiftStatus.CLOSED
    db.add(shift)
    await db.flush()
    logger.info("Закрыта смена id=%s павильон=%s", shift.id, shift.pavilion)
    return _shift_to_response(shift)


# --- Таблица кассы (редактируемые строки: ФИО, заявление, госпошлина, ДКП, страховка, номера, итого) ---

def _cash_row_to_dict(row: CashRow) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "client_name": row.client_name or "",
        "application": float(row.application),
        "state_duty": float(row.state_duty),
        "dkp": float(row.dkp),
        "insurance": float(row.insurance),
        "plates": float(row.plates),
        "total": float(row.total),
    }


@router.get("/rows", response_model=list)
async def list_cash_rows(
    limit: int = Query(500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Список строк таблицы кассы (последние сверху)."""
    q = select(CashRow).order_by(CashRow.created_at.desc()).limit(limit)
    r = await db.execute(q)
    rows = r.scalars().all()
    return [_cash_row_to_dict(row) for row in rows]


@router.post("/rows", response_model=dict)
async def create_cash_row(
    body: CashRowCreate,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Добавить строку в таблицу кассы."""
    row = CashRow(
        client_name=body.client_name or "",
        application=body.application,
        state_duty=body.state_duty,
        dkp=body.dkp,
        insurance=body.insurance,
        plates=body.plates,
        total=body.total,
    )
    db.add(row)
    await db.flush()
    return _cash_row_to_dict(row)


@router.patch("/rows/{row_id}", response_model=dict)
async def update_cash_row(
    row_id: int,
    body: CashRowUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Обновить ячейки строки кассы (передавать только изменённые поля)."""
    r = await db.execute(select(CashRow).where(CashRow.id == row_id))
    row = r.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Строка не найдена")
    if body.client_name is not None:
        row.client_name = body.client_name
    if body.application is not None:
        row.application = body.application
    if body.state_duty is not None:
        row.state_duty = body.state_duty
    if body.dkp is not None:
        row.dkp = body.dkp
    if body.insurance is not None:
        row.insurance = body.insurance
    if body.plates is not None:
        row.plates = body.plates
    if body.total is not None:
        row.total = body.total
    db.add(row)
    await db.flush()
    return _cash_row_to_dict(row)


@router.delete("/rows/{row_id}", status_code=204)
async def delete_cash_row(
    row_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Удалить строку из таблицы кассы."""
    r = await db.execute(select(CashRow).where(CashRow.id == row_id))
    row = r.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Строка не найдена")
    await db.delete(row)
    await db.flush()


# --- Касса номеров: Фамилия и Сумма (под тем же /cash/, чтобы nginx не трогать) ---

class PlateCashRowCreate(BaseModel):
    client_name: str = ""
    amount: float = 0


class PlateCashRowUpdate(BaseModel):
    client_name: Optional[str] = None
    amount: Optional[float] = None


def _plate_row_to_dict(row: PlateCashRow) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "client_name": row.client_name or "",
        "amount": float(row.amount),
    }


@router.get("/plate-rows")
async def list_plate_cash_rows(
    limit: int = Query(500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequirePlateAccess),
):
    """Список строк кассы номеров (последние сверху)."""
    q = select(PlateCashRow).order_by(PlateCashRow.created_at.desc()).limit(limit)
    r = await db.execute(q)
    rows = r.scalars().all()
    total = sum(float(row.amount) for row in rows)
    return {"rows": [_plate_row_to_dict(row) for row in rows], "total": total}


@router.post("/plate-rows")
async def create_plate_cash_row(
    body: PlateCashRowCreate,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequirePlateAccess),
):
    """Добавить строку в кассу номеров (сумма может быть отрицательной)."""
    row = PlateCashRow(
        client_name=(body.client_name or "").strip(),
        amount=Decimal(str(body.amount)),
    )
    db.add(row)
    await db.flush()
    return _plate_row_to_dict(row)


@router.patch("/plate-rows/{row_id}")
async def update_plate_cash_row(
    row_id: int,
    body: PlateCashRowUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequirePlateAccess),
):
    """Обновить строку кассы номеров."""
    r = await db.execute(select(PlateCashRow).where(PlateCashRow.id == row_id))
    row = r.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Строка не найдена")
    if body.client_name is not None:
        row.client_name = body.client_name.strip()
    if body.amount is not None:
        row.amount = Decimal(str(body.amount))
    db.add(row)
    await db.flush()
    return _plate_row_to_dict(row)


@router.delete("/plate-rows/{row_id}", status_code=204)
async def delete_plate_cash_row(
    row_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequirePlateAccess),
):
    """Удалить строку кассы номеров."""
    r = await db.execute(select(PlateCashRow).where(PlateCashRow.id == row_id))
    row = r.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Строка не найдена")
    await db.delete(row)
    await db.flush()


# --- Реестр выдачи денег за номера (пав.1 -> пав.2) ---


def _payout_to_dict(row: PlatePayout) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "client_name": row.client_name or "",
        "amount": float(row.amount),
        "paid_at": row.paid_at.isoformat() if row.paid_at else None,
        "paid_by_id": row.paid_by_id,
    }


@router.get("/plate-payouts")
async def list_plate_payouts(
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """Невыданные суммы за номера (для кассы павильона 1)."""
    q = select(PlatePayout).where(PlatePayout.paid_at.is_(None)).order_by(PlatePayout.created_at)
    r = await db.execute(q)
    rows = r.scalars().all()
    total = sum((row.amount for row in rows), Decimal("0"))
    return {
        "rows": [_payout_to_dict(row) for row in rows],
        "total": float(total),
    }


@router.post("/plate-payouts/pay")
async def pay_plate_payouts(
    db: AsyncSession = Depends(get_db),
    user: UserInfo = Depends(RequireCashAccess),
):
    """
    Выдать деньги оператору номеров:
    - уменьшить кассу документов на сумму всех невыплаченных номеров;
    - добавить по каждой записи строку в кассу номеров;
    - пометить записи как выплаченные.
    """
    r = await db.execute(
        select(PlatePayout).where(PlatePayout.paid_at.is_(None)).order_by(PlatePayout.created_at)
    )
    payouts = r.scalars().all()
    if not payouts:
        raise HTTPException(status_code=400, detail="Нет номеров к выдаче")

    total: Decimal = sum((p.amount for p in payouts), Decimal("0"))
    if total <= 0:
        raise HTTPException(status_code=400, detail="Сумма к выдаче нулевая")

    # Строка в кассе документов: Номера — выдача (отрицательная сумма)
    cash_row = CashRow(
        client_name="Номера — выдача",
        application=Decimal("0"),
        state_duty=Decimal("0"),
        dkp=Decimal("0"),
        insurance=Decimal("0"),
        plates=-total,
        total=-total,
    )
    db.add(cash_row)

    now = datetime.utcnow()

    # В кассу номеров — по человеку отдельная строка
    for p in payouts:
        db.add(
            PlateCashRow(
                client_name=p.client_name,
                amount=p.amount,
            )
        )
        p.paid_at = now
        p.paid_by_id = user.id
        db.add(p)

    await db.flush()
    logger.info("Выдача денег за номера: строк=%s сумма=%s", len(payouts), total)
    return {"count": len(payouts), "total": float(total)}
