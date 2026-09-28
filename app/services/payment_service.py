import uuid
import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.services.booking_service import get_owned_booking, transition_booking

log = structlog.get_logger()


async def create_simulated_payment(db: AsyncSession, booking_id, user_id, outcome: PaymentStatus | None = None):
    booking = await get_owned_booking(db, booking_id, user_id)
    if booking.status != BookingStatus.PENDING:
        raise RuntimeError("Booking is not payable")
    if await db.scalar(select(Payment.id).where(Payment.booking_id == booking.id)):
        raise RuntimeError("A payment attempt already exists")
    outcome = outcome or (PaymentStatus.SUCCESS if uuid.uuid4().int % 2 else PaymentStatus.FAILED)
    payment = Payment(booking_id=booking.id, amount=booking.amount, status=outcome)
    transition_booking(booking, BookingStatus.CONFIRMED if outcome == PaymentStatus.SUCCESS else BookingStatus.FAILED)
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    log.info("payment_simulated", payment_id=str(payment.id), booking_id=str(booking.id), status=outcome.value)
    return payment


async def process_webhook(db: AsyncSession, provider_event_id: str, payment_id, status: PaymentStatus):
    payment = await db.get(Payment, payment_id)
    if payment is None:
        raise LookupError("Payment not found")
    booking = await db.get(Booking, payment.booking_id, with_for_update=True)
    if booking is None:
        raise LookupError("Booking not found")
    payment.provider_event_id = provider_event_id
    payment.status = status
    target = BookingStatus.CONFIRMED if status == PaymentStatus.SUCCESS else BookingStatus.FAILED
    if booking.status == BookingStatus.PENDING:
        transition_booking(booking, target)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        # The unique provider event ID makes concurrent/replayed delivery a no-op.
        return False
    log.info("webhook_processed", provider_event_id=provider_event_id, payment_id=str(payment.id), status=status.value)
    return True
