from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.centre import Centre
from app.models.test import Test
from app.models.centre_test import CentreTest
from app.schemas.catalogue import TestCreate, CentreCreate, CentreTestCreate, CentreTestUpdate
from fastapi import HTTPException, status

def get_tests(db: Session, page: int = 1, page_size: int = 10):
    query = db.query(Test)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}

def create_test(db: Session, data: TestCreate):
    existing = db.query(Test).filter(Test.name == data.name).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Test name already exists")
    test = Test(name=data.name, description=data.description)
    db.add(test)
    db.commit()
    db.refresh(test)
    return test

def get_centres(db: Session, page: int = 1, page_size: int = 10, location: str = None, test_id: int = None):
    query = db.query(Centre)
    if location:
        query = query.filter(func.lower(Centre.location).contains(location.lower()))
    if test_id:
        query = query.join(CentreTest).filter(CentreTest.test_id == test_id)
    
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}

def create_centre(db: Session, data: CentreCreate):
    centre = Centre(name=data.name, location=data.location, address=data.address)
    db.add(centre)
    db.commit()
    db.refresh(centre)
    return centre

def get_centre(db: Session, centre_id: int):
    centre = db.query(Centre).filter(Centre.id == centre_id).first()
    if not centre:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centre not found")
    return centre

def add_test_to_centre(db: Session, centre_id: int, data: CentreTestCreate):
    centre = get_centre(db, centre_id)
    test = db.query(Test).filter(Test.id == data.test_id).first()
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
        
    existing = db.query(CentreTest).filter(CentreTest.centre_id == centre_id, CentreTest.test_id == data.test_id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Centre already offers this test")
        
    ct = CentreTest(centre_id=centre_id, test_id=data.test_id, price=data.price)
    db.add(ct)
    db.commit()
    db.refresh(ct)
    return ct

def update_centre_test_price(db: Session, centre_id: int, test_id: int, data: CentreTestUpdate):
    ct = db.query(CentreTest).filter(CentreTest.centre_id == centre_id, CentreTest.test_id == test_id).first()
    if not ct:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centre test not found")
    ct.price = data.price
    db.commit()
    db.refresh(ct)
    return ct
