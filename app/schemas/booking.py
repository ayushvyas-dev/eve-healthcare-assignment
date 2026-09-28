from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict
from app.models.booking import BookingStatus


class BookingCreate(BaseModel):
    test_id: UUID
    centre_id: UUID
    appointment_time: datetime


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    test_id: UUID
    centre_id: UUID
    appointment_time: datetime
    amount: Decimal
    status: BookingStatus
    created_at: datetime
    updated_at: datetime
