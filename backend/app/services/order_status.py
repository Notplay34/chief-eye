from app.models import OrderStatus

ALLOWED_TRANSITIONS: dict[OrderStatus, list[OrderStatus]] = {
    OrderStatus.CREATED: [OrderStatus.AWAITING_PAYMENT, OrderStatus.PROBLEM],
    OrderStatus.AWAITING_PAYMENT: [OrderStatus.PAID, OrderStatus.PROBLEM],
    OrderStatus.PAID: [
        OrderStatus.PLATE_IN_PROGRESS,
        OrderStatus.COMPLETED,
        OrderStatus.PROBLEM,
    ],
    OrderStatus.PLATE_IN_PROGRESS: [OrderStatus.PLATE_READY, OrderStatus.COMPLETED, OrderStatus.PROBLEM],
    OrderStatus.PLATE_READY: [OrderStatus.COMPLETED, OrderStatus.PROBLEM],
    OrderStatus.COMPLETED: [],
    OrderStatus.PROBLEM: [],
}


def can_transition(current: OrderStatus, new: OrderStatus) -> bool:
    return new in ALLOWED_TRANSITIONS.get(current, [])
