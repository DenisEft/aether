"""Tests for ai_pipeline — IntentClassification + EntityExtraction + AIDocumentPipeline."""

import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai_pipeline import (
    IntentClassificationService,
    EntityExtractionService,
    AIDocumentPipeline,
)
from app.models.ai import Intent
from app.models.documents import Template


@pytest.mark.asyncio
class TestIntentClassificationService:
    """Tests for intent classification."""

    async def test_classify_order_intent(
        self, async_session: AsyncSession, test_tenant_id, test_intent_order, test_template_order,
    ):
        """Text 'Новый заказ на перевозку угля' → order_new intent."""
        service = IntentClassificationService(async_session)

        # Use flush, not commit — session is in a transaction
        async_session.add(test_intent_order)
        async_session.add(test_template_order)
        await async_session.flush()

        intent, template, confidence = await service.classify(
            "Новый заказ на перевозку угля", test_tenant_id,
        )

        assert intent is not None
        assert intent.name == "order_new"
        assert template.document_type == "order"
        assert confidence > 0.0

    async def test_classify_invoice_intent(
        self, async_session: AsyncSession, test_tenant_id, test_intent_invoice, test_template_invoice,
    ):
        """Text 'Выставлен счёт на оплату №123' → invoice_request intent."""
        service = IntentClassificationService(async_session)

        async_session.add(test_intent_invoice)
        async_session.add(test_template_invoice)
        await async_session.flush()

        intent, template, confidence = await service.classify(
            "Выставлен счёт на оплату №123", test_tenant_id,
        )

        assert intent is not None
        assert intent.name == "invoice_request"
        assert template.document_type == "invoice"
        assert confidence > 0.0

    async def test_classify_no_match(self, async_session: AsyncSession):
        """Text 'привет как дела' — no intent match."""
        service = IntentClassificationService(async_session)

        intent, template, confidence = await service.classify(
            "привет как дела", uuid4(),
        )

        assert intent is None
        assert template is None
        assert confidence == 0.0


@pytest.mark.asyncio
class TestEntityExtractionService:
    """Tests for entity extraction."""

    async def test_extract_email(self, async_session: AsyncSession):
        """Extract email from text."""
        service = EntityExtractionService(async_session)

        text = "Отправить на info@company.ru"
        fields = await service.extract(text, None)

        assert "email" in fields
        assert fields["email"] == "info@company.ru"

    async def test_extract_phone(self, async_session: AsyncSession):
        """Extract phone number from text."""
        service = EntityExtractionService(async_session)

        text = "Телефон +7 914 123-45-67"
        fields = await service.extract(text, None)

        assert "phone" in fields
        assert "+7 914 123-45-67" in str(fields["phone"])

    async def test_extract_money(self, async_session: AsyncSession):
        """Extract monetary amount from text."""
        service = EntityExtractionService(async_session)

        text = "Сумма: 15000 руб"
        fields = await service.extract(text, None)

        assert "money" in fields
        assert "15000 руб" in str(fields["money"])

    async def test_extract_weight(self, async_session: AsyncSession):
        """Extract cargo weight from text."""
        service = EntityExtractionService(async_session)

        text = "Груз 70 тн"
        fields = await service.extract(text, None)

        assert "weight" in fields
        assert fields["weight"] == "70 тн"

    async def test_extract_template_fields(
        self, async_session: AsyncSession, test_template_order,
    ):
        """Extraction using template fields with patterns."""
        service = EntityExtractionService(async_session)

        async_session.add(test_template_order)
        await async_session.flush()

        text = "Груз уголь 70 тн, сумма 15000 руб"
        fields = await service.extract(text, test_template_order)

        # Built-in extractors pick up weight and money
        assert "weight" in fields
        assert "money" in fields
        assert "70" in str(fields["weight"])
        assert fields["money"] == "15000 руб"


@pytest.mark.asyncio
class TestAIDocumentPipeline:
    """End-to-end pipeline tests."""

    async def test_pipeline_process_order(
        self, async_session: AsyncSession, test_tenant_id, test_intent_order, test_template_order,
    ):
        """Full pipeline: message → classified → extracted → document."""
        pipeline = AIDocumentPipeline(async_session)

        async_session.add(test_intent_order)
        async_session.add(test_template_order)
        await async_session.flush()

        result = await pipeline.process_message(
            text="Новый заказ: груз уголь 70 тн, сумма 15000 руб",
            tenant_id=test_tenant_id,
            source="manual",
        )

        assert result["intent"] is not None
        assert result["intent"].name == "order_new"
        assert result["template"] is not None
        assert result["document"] is not None
        assert result["document"].type == "order"
        assert result["document"].fields

        # Document should have extracted fields
        assert "weight" in result["document"].fields or "money" in result["document"].fields
