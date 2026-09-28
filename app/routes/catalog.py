from fastapi import APIRouter, Depends, HTTPException, Query, status
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.centre import DiagnosticCentre
from app.models.test import DiagnosticTest
from app.schemas.centre import CentreCreate, CentreDetail, CentreOut
from app.schemas.common import Page
from app.schemas.test import TestCreate, TestOut

centres = APIRouter(prefix="/centres", tags=["diagnostic centres"])
tests = APIRouter(prefix="/tests", tags=["diagnostic tests"])


@centres.post("", response_model=CentreOut, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@centres.post("/", response_model=CentreOut, status_code=status.HTTP_201_CREATED)
async def create_centre(payload: CentreCreate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    centre = DiagnosticCentre(name=payload.name.strip(), location=payload.location.strip())
    if not centre.name or not centre.location:
        raise HTTPException(422, detail="Name and location must not be blank")
    db.add(centre)
    await db.commit()
    await db.refresh(centre)
    return centre


@centres.get("", response_model=Page[CentreOut], include_in_schema=False)
@centres.get("/", response_model=Page[CentreOut])
async def list_centres(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(DiagnosticCentre)) or 0
    result = await db.scalars(select(DiagnosticCentre).order_by(DiagnosticCentre.name).offset((page - 1) * limit).limit(limit))
    return Page(items=list(result), page=page, limit=limit, total=total)


@centres.get("/{centre_id}", response_model=CentreDetail)
async def get_centre(centre_id: UUID, db: AsyncSession = Depends(get_db)):
    centre = await db.scalar(select(DiagnosticCentre).options(selectinload(DiagnosticCentre.tests)).where(DiagnosticCentre.id == centre_id))
    if centre is None:
        raise HTTPException(404, detail={"code": "CENTRE_NOT_FOUND", "message": "Centre not found."})
    return centre


@centres.post("/{centre_id}/tests/", response_model=TestOut, status_code=status.HTTP_201_CREATED)
async def create_test(centre_id: UUID, payload: TestCreate, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    centre = await db.get(DiagnosticCentre, centre_id)
    if centre is None:
        raise HTTPException(404, detail={"code": "CENTRE_NOT_FOUND", "message": "Centre not found."})
    test = DiagnosticTest(centre_id=centre.id, name=payload.name.strip(), price=payload.price)
    if not test.name:
        raise HTTPException(422, detail="Test name must not be blank")
    db.add(test)
    await db.commit()
    await db.refresh(test)
    return test


@tests.get("", response_model=Page[TestOut], include_in_schema=False)
@tests.get("/", response_model=Page[TestOut])
async def list_tests(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), centre_id: UUID | None = None, db: AsyncSession = Depends(get_db)):
    query = select(DiagnosticTest)
    count_query = select(func.count()).select_from(DiagnosticTest)
    if centre_id:
        query, count_query = query.where(DiagnosticTest.centre_id == centre_id), count_query.where(DiagnosticTest.centre_id == centre_id)
    total = await db.scalar(count_query) or 0
    result = await db.scalars(query.order_by(DiagnosticTest.name).offset((page - 1) * limit).limit(limit))
    return Page(items=list(result), page=page, limit=limit, total=total)


@tests.get("/{test_id}", response_model=TestOut)
async def get_test(test_id: UUID, db: AsyncSession = Depends(get_db)):
    test = await db.get(DiagnosticTest, test_id)
    if test is None:
        raise HTTPException(404, detail={"code": "TEST_NOT_FOUND", "message": "Test not found."})
    return test
