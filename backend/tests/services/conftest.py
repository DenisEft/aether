"""Shared fixtures for document service tests.

All fixtures use transaction-level rollback — no test data leaks between tests.
"""

import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.document_service import DocumentCreate, DocumentService


@pytest.fixture
def test_tenant_id() -> str:
    """Fixed tenant ID for tests."""
    return uuid4()


@pytest.fixture
async def async_session(test_engine):
    """Create a new database session with transaction rollback.

    Each test gets a fresh transaction, rolled back after the test completes.
    """
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    session = factory()
    async with session.begin():
        yield session
        await session.rollback()


@pytest.fixture
async def document_service(async_session, test_tenant_id):
    """DocumentService with a test session."""
    return DocumentService(async_session)


@pytest.fixture
async def sample_document(document_service, test_tenant_id):
    """A pre-created document for tests that need an existing document."""
    data = DocumentCreate(
        tenant_id=test_tenant_id,
        type="order",
        title="Sample Order",
        fields={"cargo": "coal", "quantity": 10},
        source="manual",
    )
    return await document_service.create(data)
