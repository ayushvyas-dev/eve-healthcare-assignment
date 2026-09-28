import pytest
from types import SimpleNamespace
from app.models.booking import BookingStatus
from app.services.booking_service import transition_booking


@pytest.mark.parametrize("target", [BookingStatus.CONFIRMED, BookingStatus.FAILED, BookingStatus.CANCELLED])
def test_pending_transitions(target):
    booking = SimpleNamespace(status=BookingStatus.PENDING)
    transition_booking(booking, target)
    assert booking.status == target


@pytest.mark.parametrize("initial", [BookingStatus.CONFIRMED, BookingStatus.FAILED, BookingStatus.CANCELLED])
def test_terminal_states_cannot_transition(initial):
    booking = SimpleNamespace(status=initial)
    with pytest.raises(ValueError):
        transition_booking(booking, BookingStatus.CONFIRMED)
