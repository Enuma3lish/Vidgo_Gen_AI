from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime

from app.api import deps
from app.core.config import get_settings
from app.schemas.payment import PaymentCreateRequest, PaymentResponse
from app.services.ecpay.client import ECPayClient
from app.models.billing import Order
from app.models.user import User

settings = get_settings()
router = APIRouter()

# Initialize ECPay client
ecpay_client = ECPayClient(
    merchant_id=settings.ECPAY_MERCHANT_ID,
    hash_key=settings.ECPAY_HASH_KEY,
    hash_iv=settings.ECPAY_HASH_IV,
    payment_url=settings.ECPAY_PAYMENT_URL
)

@router.post("/create", response_model=PaymentResponse)
async def create_payment(
    request: PaymentCreateRequest,
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db)
):
    # 1. Verify Order Ownership
    result = await db.execute(select(Order).where(Order.order_number == request.order_id)) # Using order_number as ID for external ref
    order = result.scalars().first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        # 2. Generate ECPay Params
        merchant_trade_no = request.order_id + datetime.now().strftime('%H%M%S') # Ensure uniqueness
        merchant_trade_no = merchant_trade_no[:20]
        merchant_trade_date = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
        
        # 3. Create ECPay Data
        payment_data = ecpay_client.create_payment(
            merchant_trade_no=merchant_trade_no,
            merchant_trade_date=merchant_trade_date,
            total_amount=request.amount,
            trade_desc=request.description,
            item_name=request.item_name,
            return_url=f"http://localhost:8000{settings.API_V1_STR}/payments/callback",  # Backend Callback
            order_result_url="http://localhost:3000/payment/result",  # Payment result page
            client_back_url="http://localhost:3000/payment/result",  # Frontend Return
            choose_payment=request.payment_method
        )
        
        return {
            "success": True,
            "payment_url": payment_data['action_url'],
            "form_data": payment_data['params'],
            "message": "Payment created"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/callback")
async def payment_callback(request: Request, db: AsyncSession = Depends(deps.get_db)):
    form_data = await request.form()
    data = dict(form_data)
    
    if not ecpay_client.verify_callback(data.copy()):
        return "0|CheckMacValue Error"
    
    # Process Success
    if data.get('RtnCode') == '1':
        # Find Order (Extract original ID from MerchantTradeNo if needed, logic simplified here)
        # In prod we'd map MerchantTradeNo back to Order ID via Redis or DB
        return "1|OK"
        
    return "0|Error"
