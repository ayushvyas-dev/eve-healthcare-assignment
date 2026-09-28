from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.payment import PaymentStatus


class PaymentCreate(BaseModel):
    booking_id: UUID


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    booking_id: UUID
    status: PaymentStatus
    amount: Decimal


class WebhookEvent(BaseModel):
    provider_event_id: str = Field(min_length=1, max_length=255)
    payment_id: UUID
    status: PaymentStatus
