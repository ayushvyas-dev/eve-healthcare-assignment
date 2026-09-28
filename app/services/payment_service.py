import uuid
import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.models.payment_event import PaymentWebhookEvent
from app.services.booking_service import get_owned_booking, transition_booking

log = structlog.get_logger()


class WebhookConflictError(ValueError):
    """An event ID was reused with a different payment result."""


def choose_simulated_outcome() -> PaymentStatus:
    return PaymentStatus.SUCCESS if uuid.uuid4().int % 2 else PaymentStatus.FAILED


async def create_simulated_payment(db: AsyncSession, booking_id, user_id, outcome: PaymentStatus | None = None):
    booking = await get_owned_booking(db, booking_id, user_id, for_update=True)
    if booking.status != BookingStatus.PENDING:
        raise RuntimeError("Booking is not payable")
    if await db.scalar(select(Payment.id).where(Payment.booking_id == booking.id)):
        raise RuntimeError("A payment attempt already exists")
    outcome = choose_simulated_outcome() if outcome is None else outcome
    payment = Payment(booking_id=booking.id, amount=booking.amount, status=outcome)
    transition_booking(booking, BookingStatus.CONFIRMED if outcome == PaymentStatus.SUCCESS else BookingStatus.FAILED)
    db.add(payment)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise RuntimeError("A payment attempt already exists") from exc
    await db.refresh(payment)
    log.info("payment_simulated", payment_id=str(payment.id), booking_id=str(booking.id), status=outcome.value)
    return payment


async def process_webhook(db: AsyncSession, provider_event_id: str, payment_id, status: PaymentStatus):
    existing_event = await db.scalar(
        select(PaymentWebhookEvent).where(PaymentWebhookEvent.provider_event_id == provider_event_id)
    )
    if existing_event is not None:
        if existing_event.payment_id == payment_id and existing_event.status == status.value:
            return False
        raise WebhookConflictError("Provider event ID was already used for a different result.")

    # Support events accepted before the event ledger was introduced.
    legacy_event = await db.scalar(select(Payment).where(Payment.provider_event_id == provider_event_id))
    if legacy_event is not None:
        if legacy_event.id == payment_id and legacy_event.status == status:
            return False
        raise WebhookConflictError("Provider event ID was already used for a different result.")

    payment = await db.get(Payment, payment_id, with_for_update=True)
    if payment is None:
        raise LookupError("Payment not found")
    booking = await db.get(Booking, payment.booking_id, with_for_update=True)
    if booking is None:
        raise LookupError("Booking not found")

    target = BookingStatus.CONFIRMED if status == PaymentStatus.SUCCESS else BookingStatus.FAILED
    if payment.status in (PaymentStatus.SUCCESS, PaymentStatus.FAILED) and payment.status != status:
        raise WebhookConflictError("Payment already has a different final result.")
    if booking.status not in (BookingStatus.PENDING, target):
        raise WebhookConflictError("Booking already has a different final result.")

    if booking.status == BookingStatus.PENDING:
        transition_booking(booking, target)
    payment.provider_event_id = provider_event_id
    payment.status = status
    db.add(PaymentWebhookEvent(provider_event_id=provider_event_id, payment_id=payment.id, status=status.value))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        # Concurrent deliveries race on the unique event ID. Confirm that this
        # was the replay constraint before treating the failed transaction as a no-op.
        existing_event = await db.scalar(
            select(PaymentWebhookEvent).where(PaymentWebhookEvent.provider_event_id == provider_event_id)
        )
        if existing_event is not None:
            if existing_event.payment_id == payment_id and existing_event.status == status.value:
                return False
            raise WebhookConflictError("Provider event ID was already used for a different result.")
        raise
    log.info("webhook_processed", provider_event_id=provider_event_id, payment_id=str(payment.id), status=status.value)
    return True
