from fastapi import APIRouter, Depends, HTTPException, Query, status
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.booking import Booking
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingOut
from app.schemas.common import Page
from app.services.booking_service import create_booking, get_owned_booking

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("/", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
async def post_booking(payload: BookingCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return await create_booking(db, user.id, payload.test_id, payload.centre_id, payload.appointment_time)
    except LookupError as exc:
        raise HTTPException(404, detail={"code": "CATALOG_ITEM_NOT_FOUND", "message": str(exc)})
    except ValueError as exc:
        raise HTTPException(400, detail={"code": "INVALID_BOOKING", "message": str(exc)})


@router.get("/", response_model=Page[BookingOut])
async def list_bookings(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    total = await db.scalar(select(func.count()).select_from(Booking).where(Booking.user_id == user.id)) or 0
    result = await db.scalars(select(Booking).where(Booking.user_id == user.id).order_by(Booking.created_at.desc()).offset((page - 1) * limit).limit(limit))
    return Page(items=list(result), page=page, limit=limit, total=total)


@router.get("/{booking_id}", response_model=BookingOut)
async def get_booking(booking_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return await get_owned_booking(db, booking_id, user.id)
    except LookupError:
        raise HTTPException(404, detail={"code": "BOOKING_NOT_FOUND", "message": "Booking not found."})
    except PermissionError:
        raise HTTPException(403, detail={"code": "NOT_BOOKING_OWNER", "message": "You do not own this booking."})
