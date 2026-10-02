from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.schemas.catalogue import (
    CentreOut, CentreCreate, CentreWithTestsOut,
    CentreTestCreate, CentreTestOut, CentreTestUpdate, PaginatedResponse
)
from app.dependencies import require_admin
from app.services import catalogue_service

router = APIRouter(prefix="/centres", tags=["centres"])

@router.get("", response_model=PaginatedResponse[CentreOut])
def get_centres(
    location: Optional[str] = None,
    test_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    return catalogue_service.get_centres(db, page=page, page_size=page_size, location=location, test_id=test_id)

@router.post("", response_model=CentreOut, status_code=status.HTTP_201_CREATED)
def create_centre(
    data: CentreCreate,
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):
    return catalogue_service.create_centre(db, data)

@router.get("/{centre_id}", response_model=CentreWithTestsOut)
def get_centre(centre_id: int, db: Session = Depends(get_db)):
    return catalogue_service.get_centre(db, centre_id)

@router.post("/{centre_id}/tests", response_model=CentreTestOut, status_code=status.HTTP_201_CREATED)
def add_test_to_centre(
    centre_id: int,
    data: CentreTestCreate,
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):
    return catalogue_service.add_test_to_centre(db, centre_id, data)

@router.patch("/{centre_id}/tests/{test_id}", response_model=CentreTestOut)
def update_centre_test_price(
    centre_id: int,
    test_id: int,
    data: CentreTestUpdate,
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):
    return catalogue_service.update_centre_test_price(db, centre_id, test_id, data)
