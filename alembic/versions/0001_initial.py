"""Initial schema."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("email", sa.String(255), nullable=False), sa.Column("hashed_password", sa.String(255), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("diagnostic_centres", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("name", sa.String(255), nullable=False), sa.Column("location", sa.String(255), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("diagnostic_tests", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("centre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("diagnostic_centres.id"), nullable=False), sa.Column("name", sa.String(255), nullable=False), sa.Column("price", sa.Numeric(10, 2), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.CheckConstraint("price > 0", name="ck_diagnostic_test_price_positive"))
    op.create_index("ix_diagnostic_tests_centre_id", "diagnostic_tests", ["centre_id"])
    op.create_table("bookings", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False), sa.Column("test_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("diagnostic_tests.id"), nullable=False), sa.Column("centre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("diagnostic_centres.id"), nullable=False), sa.Column("appointment_time", sa.DateTime(timezone=True), nullable=False), sa.Column("amount", sa.Numeric(10, 2), nullable=False), sa.Column("status", sa.Enum("PENDING", "CONFIRMED", "FAILED", "CANCELLED", name="booking_status"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_bookings_user_id", "bookings", ["user_id"])
    op.create_index("ix_bookings_status", "bookings", ["status"])
    op.create_table("payments", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("booking_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bookings.id"), nullable=False), sa.Column("provider_event_id", sa.String(255), nullable=True), sa.Column("status", sa.Enum("PENDING", "SUCCESS", "FAILED", name="payment_status"), nullable=False), sa.Column("amount", sa.Numeric(10, 2), nullable=False), sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("last_attempt_at", sa.DateTime(timezone=True)), sa.Column("next_retry_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("provider_event_id", name="uq_payments_provider_event_id"))
    op.create_index("ix_payments_booking_id", "payments", ["booking_id"])


def downgrade():
    op.drop_table("payments")
    op.drop_table("bookings")
    op.drop_index("ix_diagnostic_tests_centre_id", table_name="diagnostic_tests")
    op.drop_table("diagnostic_tests")
    op.drop_table("diagnostic_centres")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
