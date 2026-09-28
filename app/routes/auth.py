from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.auth import AuthInput, TokenOut, UserOut
from app.dependencies.rate_limit import login_rate_limit
from app.services.auth_service import DuplicateEmailError, authenticate_user, register_user

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def signup(payload: AuthInput, db: AsyncSession = Depends(get_db)):
    try:
        user = await register_user(db, payload.email, payload.password)
    except DuplicateEmailError:
        raise HTTPException(409, detail={"code": "EMAIL_ALREADY_REGISTERED", "message": "An account with this email already exists."})
    return user


@router.post("/login", response_model=TokenOut, dependencies=[Depends(login_rate_limit)])
async def login(payload: AuthInput, db: AsyncSession = Depends(get_db)):
    access_token = await authenticate_user(db, payload.email, payload.password)
    if access_token is None:
        raise HTTPException(401, detail={"code": "INVALID_CREDENTIALS", "message": "Email or password is incorrect."}, headers={"WWW-Authenticate": "Bearer"})
    return TokenOut(access_token=access_token)
