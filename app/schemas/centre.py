from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from app.schemas.common import ORMModel


class CentreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    location: str = Field(min_length=1, max_length=255)


class CentreOut(ORMModel):
    id: UUID
    name: str
    location: str
    created_at: datetime


class CentreDetail(CentreOut):
    tests: list["TestOut"] = []


from app.schemas.test import TestOut
CentreDetail.model_rebuild()
