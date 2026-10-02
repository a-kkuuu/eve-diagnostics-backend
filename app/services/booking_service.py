from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from app.models.booking import Booking, BookingStatus
from app.models.centre_test import CentreTest

ALLOWED_TRANSITIONS = {
    BookingStatus.PENDING: {BookingStatus.CONFIRMED, BookingStatus.FAILED, BookingStatus.CANCELLED},
    BookingStatus.FAILED: {BookingStatus.CONFIRMED, BookingStatus.CANCELLED},
    BookingStatus.CONFIRMED: {BookingStatus.CANCELLED},
    BookingStatus.CANCELLED: set()
}

def change_status(booking: Booking, new_status: BookingStatus) -> Booking:
    current_status = BookingStatus(booking.status)
    if new_status not in ALLOWED_TRANSITIONS.get(current_status, set()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot transition booking from {current_status.value} to {new_status.value}"
        )
    booking.status = new_status.value
    return booking

def get_booking_for_update(db: Session, booking_id: int, user_id: int) -> Booking:
    booking = db.query(Booking).filter(Booking.id == booking_id).with_for_update().first()
    if not booking or booking.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return booking

def get_booking(db: Session, booking_id: int, user_id: int) -> Booking:
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking or booking.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return booking

from sqlalchemy.orm import selectinload

def find_active_duplicate(db: Session, user_id: int, centre_id: int, test_id: int, appointment_at):
    return db.query(Booking).filter(
        Booking.user_id == user_id,
        Booking.centre_id == centre_id,
        Booking.test_id == test_id,
        Booking.appointment_at == appointment_at,
        Booking.status.in_([BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value])
    ).first()

def create_booking(db: Session, user_id: int, centre_id: int, test_id: int, appointment_at) -> Booking:
    ct = db.query(CentreTest).filter(CentreTest.centre_id == centre_id, CentreTest.test_id == test_id).first()
    if not ct:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centre does not offer this test")
    
    if find_active_duplicate(db, user_id, centre_id, test_id, appointment_at):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Active booking already exists for this slot")
    
    booking = Booking(
        user_id=user_id,
        centre_id=centre_id,
        test_id=test_id,
        appointment_at=appointment_at,
        amount=ct.price,
        status=BookingStatus.PENDING.value
    )
    db.add(booking)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Active booking already exists for this slot")
    
    db.commit()
    db.refresh(booking)
    return booking

def get_user_bookings(db: Session, user_id: int, page: int = 1, page_size: int = 10, status_filter: str = None):
    query = db.query(Booking).options(
        selectinload(Booking.centre),
        selectinload(Booking.test)
    ).filter(Booking.user_id == user_id)
    if status_filter:
        query = query.filter(Booking.status == status_filter)
    
    query = query.order_by(Booking.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}

def cancel_booking(db: Session, booking_id: int, user_id: int):
    from datetime import datetime, timezone
    booking = get_booking_for_update(db, booking_id, user_id)
    if booking.appointment_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Appointment time has already passed")
    change_status(booking, BookingStatus.CANCELLED)
    db.commit()
    db.refresh(booking)
    return booking
