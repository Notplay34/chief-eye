from pydantic import BaseModel


class PayOrderResponse(BaseModel):
    order_id: int
    public_id: str
    status: str
    message: str = "Оплата принята"
