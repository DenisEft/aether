"""Tests for DocumentService — core business logic.

Tests use a real test database with transaction rollback.
See conftest.py for fixture setup.
"""

import pytest
from uuid import uuid4

from app.services.document_service import (
    DocumentCreate,
    DocumentNotFoundError,
    DocumentService,
    DocumentStatusTransition,
    DocumentUpdate,
    InvalidStatusTransitionError,
)


@pytest.mark.asyncio
class TestDocumentCreate:
    """Document creation tests."""

    async def test_create_document_minimal(self, document_service: DocumentService, test_tenant_id):
        """Create a document with minimal required fields."""
        data = DocumentCreate(tenant_id=test_tenant_id, type="order")
        doc = await document_service.create(data)

        assert doc.id is not None
        assert doc.type == "order"
        assert doc.status == "new"
        assert doc.version == 1
        assert doc.source == "manual"
        assert doc.fields == {}
        assert doc.is_deleted is False

    async def test_create_document_with_fields(self, document_service, test_tenant_id):
        """Create a document with custom fields."""
        data = DocumentCreate(
            tenant_id=test_tenant_id,
            type="order",
            title="Test Order",
            fields={"cargo": "coal", "quantity": 3},
            source="telegram",
        )
        doc = await document_service.create(data)

        assert doc.title == "Test Order"
        assert doc.fields == {"cargo": "coal", "quantity": 3}
        assert doc.source == "telegram"

    async def test_create_creates_version_snapshot(self, document_service, test_tenant_id):
        """Creating a document must create an initial version record."""
        data = DocumentCreate(tenant_id=test_tenant_id, type="order", fields={"x": 1})
        doc = await document_service.create(data)

        versions = await document_service.get_versions(doc.id, test_tenant_id)
        assert len(versions) == 1
        assert versions[0].version == 1
        assert versions[0].fields_snapshot == {"x": 1}
        assert versions[0].status == "new"

    async def test_create_different_types(self, document_service, test_tenant_id):
        """Documents can be of any type string."""
        for doc_type in ("order", "invoice", "request", "custom_type"):
            data = DocumentCreate(tenant_id=test_tenant_id, type=doc_type)
            doc = await document_service.create(data)
            assert doc.type == doc_type


@pytest.mark.asyncio
class TestDocumentGet:
    """Document retrieval tests."""

    async def test_get_existing(self, document_service, sample_document):
        """Get an existing document by ID."""
        doc = await document_service.get(sample_document.id, sample_document.tenant_id)
        assert doc.id == sample_document.id
        assert doc.type == sample_document.type

    async def test_get_nonexistent_raises(self, document_service, test_tenant_id):
        """Getting a non-existent document raises DocumentNotFoundError."""
        with pytest.raises(DocumentNotFoundError):
            await document_service.get(uuid4(), test_tenant_id)

    async def test_get_deleted_raises(self, document_service, sample_document):
        """Getting a soft-deleted document raises DocumentNotFoundError."""
        await document_service.soft_delete(sample_document.id, sample_document.tenant_id)
        with pytest.raises(DocumentNotFoundError):
            await document_service.get(sample_document.id, sample_document.tenant_id)


@pytest.mark.asyncio
class TestDocumentUpdate:
    """Document update tests."""

    async def test_update_fields(self, document_service, sample_document):
        """Updating fields creates a new version."""
        data = DocumentUpdate(fields={"cargo": "iron ore", "quantity": 5})
        doc = await document_service.update(
            sample_document.id, sample_document.tenant_id, data
        )

        assert doc.fields == {"cargo": "iron ore", "quantity": 5}
        assert doc.version == 2  # Bumped from 1

        # Version snapshot created
        versions = await document_service.get_versions(doc.id, doc.tenant_id)
        assert len(versions) == 2
        assert versions[0].version == 2  # Newest first

    async def test_update_preserves_unchanged_fields(self, document_service, test_tenant_id):
        """Partial update only changes specified fields, preserves others."""
        doc = await document_service.create(
            DocumentCreate(
                tenant_id=test_tenant_id,
                type="order",
                fields={"a": 1, "b": 2, "c": 3},
            )
        )

        data = DocumentUpdate(fields={"b": 99})
        doc = await document_service.update(doc.id, test_tenant_id, data)

        assert doc.fields == {"a": 1, "b": 99, "c": 3}

    async def test_update_title(self, document_service, sample_document):
        """Updating title without changing fields."""
        data = DocumentUpdate(title="New Title")
        doc = await document_service.update(
            sample_document.id, sample_document.tenant_id, data
        )
        assert doc.title == "New Title"

    async def test_update_no_changes_skips_version(self, document_service, sample_document):
        """Updating with no actual changes does not create a new version."""
        old_version = sample_document.version
        data = DocumentUpdate(title=sample_document.title)  # Same title
        doc = await document_service.update(
            sample_document.id, sample_document.tenant_id, data
        )
        assert doc.version == old_version


@pytest.mark.asyncio
class TestStatusTransition:
    """Status transition tests."""

    async def test_transition_to_new_status(self, document_service, sample_document):
        """Transition document to a new status."""
        transition = DocumentStatusTransition(new_status="confirmed")
        doc = await document_service.transition_status(
            sample_document.id, sample_document.tenant_id, transition
        )

        assert doc.status == "confirmed"
        assert doc.version == 2

    async def test_transition_with_comment(self, document_service, sample_document):
        """Status transition can include a comment."""
        transition = DocumentStatusTransition(new_status="confirmed", comment="Approved by manager")
        doc = await document_service.transition_status(
            sample_document.id, sample_document.tenant_id, transition
        )
        assert doc.status == "confirmed"


@pytest.mark.asyncio
class TestSoftDelete:
    """Soft delete and restore tests."""

    async def test_soft_delete(self, document_service, sample_document):
        """Soft-deleting marks document as deleted."""
        doc = await document_service.soft_delete(
            sample_document.id, sample_document.tenant_id
        )

        assert doc.is_deleted is True
        assert doc.deleted_at is not None

        # Document is no longer findable via get()
        with pytest.raises(DocumentNotFoundError):
            await document_service.get(sample_document.id, sample_document.tenant_id)

    async def test_restore(self, document_service, sample_document):
        """Restoring a soft-deleted document makes it visible again."""
        await document_service.soft_delete(sample_document.id, sample_document.tenant_id)

        doc = await document_service.restore(sample_document.id, sample_document.tenant_id)
        assert doc.is_deleted is False
        assert doc.deleted_at is None

        # Document is findable again
        found = await document_service.get(doc.id, doc.tenant_id)
        assert found is not None


@pytest.mark.asyncio
class TestTags:
    """Tag management tests."""

    async def test_add_tag(self, document_service, sample_document):
        """Adding a tag to a document."""
        doc = await document_service.add_tag(
            sample_document.id, sample_document.tenant_id, "urgent"
        )

        tags = await document_service.get_tags(doc.id, doc.tenant_id)
        assert len(tags) == 1
        assert tags[0].name == "urgent"

    async def test_add_duplicate_tag_idempotent(self, document_service, sample_document):
        """Adding the same tag twice does not create duplicates."""
        await document_service.add_tag(sample_document.id, sample_document.tenant_id, "urgent")
        await document_service.add_tag(sample_document.id, sample_document.tenant_id, "urgent")

        tags = await document_service.get_tags(sample_document.id, sample_document.tenant_id)
        assert len(tags) == 1

    async def test_remove_tag(self, document_service, sample_document):
        """Removing a tag from a document."""
        await document_service.add_tag(sample_document.id, sample_document.tenant_id, "urgent")
        await document_service.remove_tag(sample_document.id, sample_document.tenant_id, "urgent")

        tags = await document_service.get_tags(sample_document.id, sample_document.tenant_id)
        assert len(tags) == 0

    async def test_multiple_tags(self, document_service, sample_document):
        """A document can have multiple tags."""
        await document_service.add_tag(sample_document.id, sample_document.tenant_id, "urgent")
        await document_service.add_tag(sample_document.id, sample_document.tenant_id, "accounting")

        tags = await document_service.get_tags(sample_document.id, sample_document.tenant_id)
        tag_names = {t.name for t in tags}
        assert tag_names == {"urgent", "accounting"}
