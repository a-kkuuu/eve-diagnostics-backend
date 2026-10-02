from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.catalogue import TestOut, TestCreate, PaginatedResponse
from app.dependencies import require_admin
from app.services import catalogue_service

router = APIRouter(prefix="/tests", tags=["tests"])

@router.get("", response_model=PaginatedResponse[TestOut])
def get_tests(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    return catalogue_service.get_tests(db, page=page, page_size=page_size)

@router.post("", response_model=TestOut, status_code=status.HTTP_201_CREATED)
def create_test(
    data: TestCreate,
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):
    return catalogue_service.create_test(db, data)
