from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class PaymentCreateRequest(BaseModel):
    order_id: str
    amount: int = Field(..., gt=0)
    item_name: str
    description: str = "Payment"
    payment_method: str = "Credit"

class PaymentResponse(BaseModel):
    success: bool
    payment_url: Optional[str] = None
    form_data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
