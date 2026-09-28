from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.centre import DiagnosticCentre
from app.models.test import DiagnosticTest


async def create_centre(db: AsyncSession, name: str, location: str) -> DiagnosticCentre:
    centre = DiagnosticCentre(name=name.strip(), location=location.strip())
    if not centre.name or not centre.location:
        raise ValueError("Name and location must not be blank")
    db.add(centre)
    await db.commit()
    await db.refresh(centre)
    return centre


async def list_centres(db: AsyncSession, page: int, limit: int) -> tuple[list[DiagnosticCentre], int]:
    total = await db.scalar(select(func.count()).select_from(DiagnosticCentre)) or 0
    result = await db.scalars(
        select(DiagnosticCentre).order_by(DiagnosticCentre.name).offset((page - 1) * limit).limit(limit)
    )
    return list(result), total


async def get_centre(db: AsyncSession, centre_id: UUID) -> DiagnosticCentre:
    centre = await db.scalar(
        select(DiagnosticCentre)
        .options(selectinload(DiagnosticCentre.tests))
        .where(DiagnosticCentre.id == centre_id)
    )
    if centre is None:
        raise LookupError("Centre not found")
    return centre


async def create_test(db: AsyncSession, centre_id: UUID, name: str, price) -> DiagnosticTest:
    centre = await db.get(DiagnosticCentre, centre_id)
    if centre is None:
        raise LookupError("Centre not found")
    test = DiagnosticTest(centre_id=centre.id, name=name.strip(), price=price)
    if not test.name:
        raise ValueError("Test name must not be blank")
    db.add(test)
    await db.commit()
    await db.refresh(test)
    return test


async def list_tests(db: AsyncSession, page: int, limit: int, centre_id: UUID | None = None) -> tuple[list[DiagnosticTest], int]:
    query = select(DiagnosticTest)
    count_query = select(func.count()).select_from(DiagnosticTest)
    if centre_id is not None:
        query = query.where(DiagnosticTest.centre_id == centre_id)
        count_query = count_query.where(DiagnosticTest.centre_id == centre_id)
    total = await db.scalar(count_query) or 0
    result = await db.scalars(query.order_by(DiagnosticTest.name).offset((page - 1) * limit).limit(limit))
    return list(result), total


async def get_test(db: AsyncSession, test_id: UUID) -> DiagnosticTest:
    test = await db.get(DiagnosticTest, test_id)
    if test is None:
        raise LookupError("Test not found")
    return test
