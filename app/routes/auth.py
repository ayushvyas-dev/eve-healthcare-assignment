from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import AuthInput, TokenOut, UserOut
from app.dependencies.rate_limit import login_rate_limit

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def signup(payload: AuthInput, db: AsyncSession = Depends(get_db)):
    user = User(email=payload.email.lower(), hashed_password=hash_password(payload.password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, detail={"code": "EMAIL_ALREADY_REGISTERED", "message": "An account with this email already exists."})
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenOut, dependencies=[Depends(login_rate_limit)])
async def login(payload: AuthInput, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(401, detail={"code": "INVALID_CREDENTIALS", "message": "Email or password is incorrect."}, headers={"WWW-Authenticate": "Bearer"})
    return TokenOut(access_token=create_access_token(str(user.id)))
