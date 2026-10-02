from pydantic import BaseModel, Field, ConfigDict, StringConstraints
from datetime import datetime
from typing import List, Optional, Annotated, TypeVar, Generic
from decimal import Decimal

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int

NameStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
PriceDecimal = Annotated[Decimal, Field(gt=0, decimal_places=2)]

class TestCreate(BaseModel):
    name: NameStr
    description: Optional[str] = None

class TestOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class CentreCreate(BaseModel):
    name: NameStr
    location: NameStr
    address: NameStr

class CentreOut(BaseModel):
    id: int
    name: str
    location: str
    address: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class CentreTestCreate(BaseModel):
    test_id: int
    price: PriceDecimal

class CentreTestUpdate(BaseModel):
    price: PriceDecimal

class CentreTestOut(BaseModel):
    id: int
    test_id: int
    price: Decimal
    created_at: datetime
    test: Optional[TestOut] = None
    model_config = ConfigDict(from_attributes=True)

class CentreWithTestsOut(CentreOut):
    tests: List[CentreTestOut] = []
