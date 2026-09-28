from typing import Generic, TypeVar
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    limit: int
    total: int


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
