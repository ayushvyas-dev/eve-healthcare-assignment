from fastapi import APIRouter, Depends, HTTPException, Query, status
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.schemas.centre import CentreCreate, CentreDetail, CentreOut
from app.schemas.common import Page
from app.schemas.test import TestCreate, TestOut
from app.services.catalog_service import (
    create_centre as create_centre_record,
    create_test as create_test_record,
    get_centre as load_centre,
    get_test as load_test,
    list_centres as load_centres,
    list_tests as load_tests,
)

centres = APIRouter(prefix="/centres", tags=["diagnostic centres"])
tests = APIRouter(prefix="/tests", tags=["diagnostic tests"])


@centres.post("", response_model=CentreOut, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@centres.post("/", response_model=CentreOut, status_code=status.HTTP_201_CREATED)
async def create_centre(payload: CentreCreate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        return await create_centre_record(db, payload.name, payload.location)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc))


@centres.get("", response_model=Page[CentreOut], include_in_schema=False)
@centres.get("/", response_model=Page[CentreOut])
async def list_centres(page: int = Query(1, ge=1), limit: int = Query(20, ge=1), db: AsyncSession = Depends(get_db)):
    limit = min(limit, 100)
    items, total = await load_centres(db, page, limit)
    return Page(items=items, page=page, limit=limit, total=total)


@centres.get("/{centre_id}", response_model=CentreDetail)
async def get_centre(centre_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        return await load_centre(db, centre_id)
    except LookupError:
        raise HTTPException(404, detail={"code": "CENTRE_NOT_FOUND", "message": "Centre not found."})


@centres.post("/{centre_id}/tests/", response_model=TestOut, status_code=status.HTTP_201_CREATED)
async def create_test(centre_id: UUID, payload: TestCreate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        return await create_test_record(db, centre_id, payload.name, payload.price)
    except LookupError:
        raise HTTPException(404, detail={"code": "CENTRE_NOT_FOUND", "message": "Centre not found."})
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc))


@tests.get("", response_model=Page[TestOut], include_in_schema=False)
@tests.get("/", response_model=Page[TestOut])
async def list_tests(page: int = Query(1, ge=1), limit: int = Query(20, ge=1), centre_id: UUID | None = None, db: AsyncSession = Depends(get_db)):
    limit = min(limit, 100)
    items, total = await load_tests(db, page, limit, centre_id)
    return Page(items=items, page=page, limit=limit, total=total)


@tests.get("/{test_id}", response_model=TestOut)
async def get_test(test_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        return await load_test(db, test_id)
    except LookupError:
        raise HTTPException(404, detail={"code": "TEST_NOT_FOUND", "message": "Test not found."})
