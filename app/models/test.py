import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class DiagnosticTest(Base):
    __tablename__ = "diagnostic_tests"
    __table_args__ = (CheckConstraint("price > 0", name="ck_diagnostic_test_price_positive"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    centre_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("diagnostic_centres.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    centre: Mapped["DiagnosticCentre"] = relationship(back_populates="tests")
