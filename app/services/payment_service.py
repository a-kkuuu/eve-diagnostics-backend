import logging
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.payment import Payment, PaymentStatus, WebhookEvent
from app.models.booking import Booking, BookingStatus
from app.services.booking_service import change_status
from app.schemas.payment import WebhookPayload

logger = logging.getLogger(__name__)

def apply_payment_result(db: Session, payment: Payment, booking: Booking, new_status: str) -> str:
    """
    Applies the result of a payment to both the payment record and the associated booking.
    Must be called within an active transaction where booking and payment are already locked for update.
    """
    if payment.status == new_status:
        return "unchanged"
        
    if payment.status in (PaymentStatus.SUCCESS.value, PaymentStatus.FAILED.value):
        logger.warning(f"Terminal payment {payment.id} received conflicting status {new_status}")
        return "ignored"
        
    if payment.status == PaymentStatus.PENDING.value:
        payment.status = new_status
        
        if new_status == PaymentStatus.SUCCESS.value:
            if booking.status in (BookingStatus.PENDING.value, BookingStatus.FAILED.value):
                change_status(booking, BookingStatus.CONFIRMED)
            elif booking.status == BookingStatus.CONFIRMED.value:
                pass # nothing
            elif booking.status == BookingStatus.CANCELLED.value:
                logger.warning(f"paid_after_cancel, refund needed: payment_id={payment.id} booking_id={booking.id}")
                
        elif new_status == PaymentStatus.FAILED.value:
            if booking.status == BookingStatus.PENDING.value:
                change_status(booking, BookingStatus.FAILED)
            # any other status -> leave it
            
        logger.info(f"result applied: payment_id={payment.id} new_status={new_status} booking_id={booking.id} booking_status={booking.status}")
        return "processed"

def process_webhook_event(db: Session, payload: WebhookPayload, raw_payload: dict) -> str:
    # We must lock the booking first, but to know the booking_id we only query the id.
    # We DO NOT load the Payment object yet to avoid stale-row risks, where an unlocked payment
    # is read into the session and a later with_for_update() might not refresh it fully if not careful.
    booking_id = db.query(Payment.booking_id).filter(Payment.provider_ref == payload.provider_ref).scalar()
    if not booking_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        
    booking = db.query(Booking).filter(Booking.id == booking_id).with_for_update().first()
    # Now that booking is locked, lock and load the payment. Use populate_existing() to ensure fresh data.
    payment = db.query(Payment).filter(Payment.provider_ref == payload.provider_ref).with_for_update().populate_existing().first()
    
    stmt = pg_insert(WebhookEvent).values(
        event_id=payload.event_id,
        provider_ref=payload.provider_ref,
        payload=raw_payload
    ).on_conflict_do_nothing(index_elements=["event_id"]).returning(WebhookEvent.id)
    
    result = db.execute(stmt)
    if result.fetchone() is None:
        logger.info(f"Duplicate event: event_id={payload.event_id}")
        db.commit()
        return "already_processed"
        
    result_status = apply_payment_result(db, payment, booking, payload.status)
    db.commit()
    
    return result_status
