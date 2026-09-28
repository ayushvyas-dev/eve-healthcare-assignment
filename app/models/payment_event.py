import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PaymentWebhookEvent(Base):
    """Durable idempotency record for each provider event ID."""

    __tablename__ = "payment_webhook_events"
    __table_args__ = (
        CheckConstraint("status IN ('SUCCESS', 'FAILED')", name="ck_webhook_event_status"),
        Index("ix_payment_webhook_events_payment_id", "payment_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider_event_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payments.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
