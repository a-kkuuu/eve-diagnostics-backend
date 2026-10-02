from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.payment import Payment, PaymentStatus, WebhookEvent
from app.models.booking import BookingStatus
from app.schemas.payment import PaymentRequest, PaymentResponse, WebhookPayload
from app.services.booking_service import get_booking_for_update
from app.services.payment_service import apply_payment_result, process_webhook_event
from app.config import settings
import hmac
import hashlib
import json
import logging
import random

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])

@router.post("/", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(request: PaymentRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Booking must be locked with FOR UPDATE BEFORE checking for existing pending payments
    # to prevent a race condition where two concurrent requests both see no pending payments.
    booking = get_booking_for_update(db, request.booking_id, current_user.id)
    
    if booking.status in (BookingStatus.CONFIRMED.value, BookingStatus.CANCELLED.value):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Booking cannot be paid")
        
    pending_payment = db.query(Payment).filter(
        Payment.booking_id == booking.id,
        Payment.status == PaymentStatus.PENDING.value
    ).first()
    
    if pending_payment:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A pending payment already exists")
        
    payment = Payment(
        booking_id=booking.id,
        amount=booking.amount,
        status=PaymentStatus.PENDING.value
    )
    db.add(payment)
    db.flush()
    logger.info(f"payment created: payment_id={payment.id} booking_id={booking.id}")
    
    simulate = request.simulate
    if not simulate:
        simulate = random.choice(["success", "failed"])
        
    if simulate != "pending":
        new_status = PaymentStatus.SUCCESS.value if simulate == "success" else PaymentStatus.FAILED.value
        apply_payment_result(db, payment, booking, new_status)
        
    db.commit()
    db.refresh(payment)
    return payment

@router.post("/webhook/")
async def webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    signature = request.headers.get("X-Signature")
    if not signature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature")
        
    expected_mac = hmac.new(settings.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature.encode(), expected_mac.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
        
    try:
        data = json.loads(body)
        payload = WebhookPayload(**data)
    except (json.JSONDecodeError, ValidationError, TypeError) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid payload")
        
    result_status = await run_in_threadpool(process_webhook_event, db, payload, data)
    return {"status": result_status}
