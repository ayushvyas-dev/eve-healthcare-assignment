from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field
from app.schemas.common import ORMModel


class TestCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class TestOut(ORMModel):
    id: UUID
    centre_id: UUID
    name: str
    price: Decimal
    created_at: datetime
