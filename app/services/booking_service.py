from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.booking import Booking, BookingStatus
from app.models.centre import DiagnosticCentre
from app.models.test import DiagnosticTest

ALLOWED_TRANSITIONS = {BookingStatus.PENDING: {BookingStatus.CONFIRMED, BookingStatus.FAILED, BookingStatus.CANCELLED}}


def transition_booking(booking: Booking, new_status: BookingStatus) -> None:
    if new_status not in ALLOWED_TRANSITIONS.get(booking.status, set()):
        raise ValueError(f"Invalid booking transition: {booking.status} -> {new_status}")
    booking.status = new_status


async def create_booking(db: AsyncSession, user_id, test_id, centre_id, appointment_time):
    test = await db.get(DiagnosticTest, test_id)
    centre = await db.get(DiagnosticCentre, centre_id)
    if test is None or centre is None:
        raise LookupError("Test or centre not found")
    if test.centre_id != centre_id:
        raise ValueError("Test is not offered by this centre")
    if appointment_time.tzinfo is None:
        appointment_time = appointment_time.replace(tzinfo=timezone.utc)
    if appointment_time <= datetime.now(timezone.utc):
        raise ValueError("Appointment time must be in the future")
    booking = Booking(user_id=user_id, test_id=test_id, centre_id=centre_id, appointment_time=appointment_time, amount=test.price, status=BookingStatus.PENDING)
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    return booking


async def get_owned_booking(db: AsyncSession, booking_id, user_id):
    booking = await db.get(Booking, booking_id)
    if booking is None:
        raise LookupError("Booking not found")
    if booking.user_id != user_id:
        raise PermissionError("Booking belongs to another user")
    return booking
