"""Track provider webhook event IDs and enforce one payment per booking."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_payment_webhook_events"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("ix_payments_booking_id", table_name="payments")
    op.create_unique_constraint("uq_payments_booking_id", "payments", ["booking_id"])
    op.create_table(
        "payment_webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider_event_id", sa.String(255), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('SUCCESS', 'FAILED')", name="ck_webhook_event_status"),
        sa.UniqueConstraint("provider_event_id", name="uq_payment_webhook_events_provider_event_id"),
    )
    op.create_index("ix_payment_webhook_events_payment_id", "payment_webhook_events", ["payment_id"])


def downgrade():
    op.drop_index("ix_payment_webhook_events_payment_id", table_name="payment_webhook_events")
    op.drop_table("payment_webhook_events")
    op.drop_constraint("uq_payments_booking_id", "payments", type_="unique")
    op.create_index("ix_payments_booking_id", "payments", ["booking_id"])
