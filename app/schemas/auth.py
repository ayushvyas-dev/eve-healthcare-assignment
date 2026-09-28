from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field
from app.schemas.common import ORMModel


class AuthInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(ORMModel):
    id: UUID
    email: EmailStr
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
