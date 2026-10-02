from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models.user import User
from app.models.booking import BookingStatus
from app.schemas.booking import BookingCreate, BookingOut
from app.schemas.catalogue import PaginatedResponse
from app.dependencies import get_current_user
from app.services import booking_service

router = APIRouter(prefix="/bookings", tags=["bookings"])

@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking(
    data: BookingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return booking_service.create_booking(
        db=db,
        user_id=current_user.id,
        centre_id=data.centre_id,
        test_id=data.test_id,
        appointment_at=data.appointment_at
    )

@router.get("", response_model=PaginatedResponse[BookingOut])
def get_bookings(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if status_filter and status_filter not in [e.value for e in BookingStatus]:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid status filter")
    return booking_service.get_user_bookings(db, current_user.id, page=page, page_size=page_size, status_filter=status_filter)

@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return booking_service.get_booking(db, booking_id, current_user.id)

@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return booking_service.cancel_booking(db, booking_id, current_user.id)
