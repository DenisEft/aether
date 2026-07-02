"""Shared fixtures for document service tests.

All fixtures use transaction-level rollback — no test data leaks between tests.
"""

import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.document_service import DocumentCreate, DocumentService
from app.services.template_service import TemplateService, TemplateCreate
from app.models.documents import Template
from app.models.ai import Intent


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


@pytest.fixture
async def template_service(async_session):
    """TemplateService with a test session."""
    return TemplateService(async_session)


@pytest.fixture
async def test_template(template_service, test_tenant_id):
    """A pre-created template for tests."""
    data = TemplateCreate(
        tenant_id=test_tenant_id,
        name="Test Template",
        document_type="order",
        fields=[
            {"key": "customer_name", "label": "Customer Name", "type": "text", "required": True},
            {"key": "amount", "label": "Amount", "type": "number", "required": False},
        ],
        description="Test template for unit tests",
        icon="📦",
    )
    return await template_service.create(data)


@pytest.fixture
def test_template_data(test_tenant_id):
    """Dict-based test template data for create tests."""
    return {
        "tenant_id": test_tenant_id,
        "name": "Test Template",
        "document_type": "order",
        "fields": [
            {"key": "customer_name", "label": "Customer Name", "type": "text", "required": True},
            {"key": "amount", "label": "Amount", "type": "number", "required": False},
        ],
        "description": "Test template for unit tests",
        "icon": "📦",
        "statuses": [
            {"key": "new", "label": "Новый", "color": "#6b7280", "is_initial": True}
        ],
    }


@pytest.fixture
async def system_template(template_service):
    """A pre-created system template (tenant_id=None)."""
    data = TemplateCreate(
        tenant_id=None,
        name="System Template",
        document_type="invoice",
        fields=[
            {"key": "invoice_number", "label": "Invoice Number", "type": "text", "required": True},
            {"key": "total", "label": "Total", "type": "number", "required": True},
        ],
        description="System template",
        icon="💰",
        is_system=True,
    )
    return await template_service.create(data)


# ── AI Pipeline fixtures ─────────────────────────────────────


@pytest.fixture
def test_intent_order(test_tenant_id):
    """A test intent for order classification."""
    return Intent(
        name="order_new",
        display_name="Новый заказ",
        category="order",
        description="Создание нового заказа",
        is_builtin=False,
        plugin_ids=[],
    )


@pytest.fixture
def test_intent_invoice(test_tenant_id):
    """A test intent for invoice classification."""
    return Intent(
        name="invoice_request",
        display_name="Счёт на оплату",
        category="invoice",
        description="Счёт на оплату",
        is_builtin=False,
        plugin_ids=[],
    )


@pytest.fixture
def test_template_order(test_tenant_id):
    """A test template for order documents with extraction patterns."""
    return Template(
        tenant_id=test_tenant_id,
        name="Заказ",
        document_type="order",
        fields=[
            {"key": "cargo", "label": "Груз", "type": "text", "required": True},
            {"key": "weight", "label": "Вес", "type": "text", "pattern": r'(\d+)[\s]*(?:тн|тонн)'},
            {"key": "amount", "label": "Сумма", "type": "text", "pattern": r'(\d+)[\s]*(?:руб|₽)'},
        ],
        statuses=[
            {"key": "new", "label": "Новый", "color": "#6b7280", "is_initial": True},
        ],
        icon="📦",
        is_system=False,
    )


@pytest.fixture
def test_template_invoice(test_tenant_id):
    """A test template for invoice documents."""
    return Template(
        tenant_id=test_tenant_id,
        name="Счёт",
        document_type="invoice",
        fields=[
            {"key": "invoice_number", "label": "Номер счёта", "type": "text", "required": True},
            {"key": "amount", "label": "Сумма", "type": "text", "pattern": r'(\d+)[\s]*(?:руб|₽)'},
        ],
        statuses=[
            {"key": "draft", "label": "Черновик", "color": "#6b7280", "is_initial": True},
        ],
        icon="💰",
        is_system=False,
    )
