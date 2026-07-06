"""Document service — business logic for document CRUD, AI pipeline, and lifecycle.

All document operations go through this service. API routers delegate here.
No business logic lives in routers — they only handle HTTP concerns.

Design principles:
- Every mutation creates a DocumentVersion snapshot and a DocumentOperation record.
- Status transitions are validated against the template's status machine.
- AI pipeline is triggered asynchronously via Celery.
- Soft delete only; hard delete requires explicit flag.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.documents import (
    Document,
    DocumentOperation,
    DocumentTag,
    DocumentVersion,
    Tag,
)

logger = logging.getLogger(__name__)


# ── Errors ───────────────────────────────────────────────────────────────────


class DocumentNotFoundError(ValueError):
    """Document with given ID does not exist."""


class DocumentLimitExceededError(ValueError):
    """Tenant has reached their document limit for the current plan."""


class InvalidStatusTransitionError(ValueError):
    """The requested status transition is not allowed by the template's status machine."""


class TemplateNotFoundError(ValueError):
    """Template with given ID does not exist."""


# ── Data Transfer ────────────────────────────────────────────────────────────


@dataclass
class DocumentCreate:
    """Input for creating a new document."""

    tenant_id: UUID
    type: str
    title: str | None = None
    fields: dict[str, Any] | None = None
    company_id: UUID | None = None
    source: str = "manual"
    source_meta: dict[str, Any] | None = None


@dataclass
class DocumentUpdate:
    """Input for updating an existing document."""

    title: str | None = None
    fields: dict[str, Any] | None = None
    company_id: UUID | None = None


@dataclass
class DocumentStatusTransition:
    """Input for transitioning document status."""

    new_status: str
    comment: str | None = None


# ── Service ──────────────────────────────────────────────────────────────────


class DocumentService:
    """Business logic for document management.

    All methods are async and require a database session.
    The session is managed externally (by FastAPI dependency injection).
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    # ── CRUD ───────────────────────────────────────────────────

    async def create(self, data: DocumentCreate, user_id: UUID | None = None) -> Document:
        """Create a new document with initial version and operation record.

        Args:
            data: Document creation parameters.
            user_id: ID of the user creating the document.

        Returns:
            The newly created Document.

        Raises:
            DocumentLimitExceededError: If tenant has reached their plan limit.
        """
        # TODO: Check plan limits when billing is wired up
        # await self._check_document_limit(data.tenant_id)

        now = datetime.now(UTC)
        document = Document(
            id=uuid4(),
            tenant_id=data.tenant_id,
            type=data.type,
            title=data.title,
            fields=data.fields or {},
            company_id=data.company_id,
            source=data.source,
            source_meta=data.source_meta,
            status="new",  # Default initial status; template may override
            version=1,
            creator_id=user_id,
            created_at=now,
            updated_at=now,
        )

        self._session.add(document)
        await self._session.flush()

        # Create initial version snapshot
        version = DocumentVersion(
            document_id=document.id,
            version=1,
            fields_snapshot=dict(document.fields),
            status=document.status,
            change_description="Document created",
            changed_by=user_id,
            created_at=now,
        )
        self._session.add(version)

        # Record operation
        operation = DocumentOperation(
            document_id=document.id,
            version=1,
            op_type="create",
            op_data={"type": document.type, "source": document.source},
            user_id=user_id,
            created_at=now,
        )
        self._session.add(operation)

        await self._session.flush()
        logger.info(
            "Document created: id=%s tenant=%s type=%s",
            document.id,
            document.tenant_id,
            document.type,
        )
        return document

    async def get(self, document_id: UUID, tenant_id: UUID) -> Document:
        """Get a document by ID, scoped to tenant.

        Raises:
            DocumentNotFoundError: If document doesn't exist or is deleted.
        """
        result = await self._session.execute(
            select(Document)
            .where(
                Document.id == document_id,
                Document.tenant_id == tenant_id,
                Document.is_deleted == False,  # noqa: E712
            )
            .options(selectinload(Document.template))
        )
        document = result.scalar_one_or_none()
        if document is None:
            raise DocumentNotFoundError(f"Document {document_id} not found")
        return document

    async def list_documents(
        self,
        tenant_id: UUID,
        *,
        type: str | None = None,
        status: str | None = None,
        company_id: UUID | None = None,
        source: str | None = None,
        search: str | None = None,
        cursor: UUID | None = None,
        limit: int = 50,
    ) -> tuple[list[Document], bool]:
        """List documents with filters and cursor-based pagination.

        Returns:
            Tuple of (documents, has_more).
        """
        conditions = [
            Document.tenant_id == tenant_id,
            Document.is_deleted == False,  # noqa: E712
        ]

        if type:
            conditions.append(Document.type == type)
        if status:
            conditions.append(Document.status == status)
        if company_id:
            conditions.append(Document.company_id == company_id)
        if source:
            conditions.append(Document.source == source)
        if cursor:
            conditions.append(Document.id < cursor)
        if search:
            # Full-text search via PostgreSQL tsvector
            conditions.append(
                text("documents.search_vector @@ plainto_tsquery('russian', :q)").bindparams(
                    q=search
                )
            )

        query = (
            select(Document)
            .where(*conditions)
            .order_by(Document.created_at.desc())
            .limit(limit + 1)  # +1 to check has_more
        )

        if search:
            query = query.order_by(
                text("ts_rank(search_vector, plainto_tsquery('russian', :q)) DESC").bindparams(
                    q=search
                )
            )

        result = await self._session.execute(query)
        documents = list(result.scalars().all())

        has_more = len(documents) > limit
        if has_more:
            documents = documents[:limit]

        return documents, has_more

    async def update(
        self,
        document_id: UUID,
        tenant_id: UUID,
        data: DocumentUpdate,
        user_id: UUID | None = None,
    ) -> Document:
        """Update document fields. Creates version snapshot and operation record.

        Raises:
            DocumentNotFoundError: If document doesn't exist.
        """
        document = await self.get(document_id, tenant_id)
        old_fields = dict(document.fields)
        now = datetime.now(UTC)
        changes: dict[str, Any] = {}

        if data.title is not None and data.title != document.title:
            changes["title"] = {"old": document.title, "new": data.title}
            document.title = data.title
        if data.fields is not None:
            changed = {}
            for key, new_val in data.fields.items():
                old_val = document.fields.get(key)
                if old_val != new_val:
                    changed[key] = {"old": old_val, "new": new_val}
            if changed:
                changes["fields"] = changed
                document.fields = {**document.fields, **data.fields}
        if data.company_id is not None:
            changes["company_id"] = {"old": str(document.company_id), "new": str(data.company_id)}
            document.company_id = data.company_id

        if changes:
            new_version = document.version + 1
            document.version = new_version
            document.updated_at = now

            # Version snapshot
            version = DocumentVersion(
                document_id=document.id,
                version=new_version,
                fields_snapshot=dict(document.fields),
                status=document.status,
                change_description=f"Updated fields: {', '.join(changes)}",
                changed_by=user_id,
                created_at=now,
            )
            self._session.add(version)

            # Operation record
            operation = DocumentOperation(
                document_id=document.id,
                version=new_version,
                op_type="field_update",
                op_data=changes,
                user_id=user_id,
                created_at=now,
            )
            self._session.add(operation)

            logger.info(
                "Document updated: id=%s version=%d changes=%s",
                document.id,
                new_version,
                list(changes),
            )

        await self._session.flush()
        return document

    async def transition_status(
        self,
        document_id: UUID,
        tenant_id: UUID,
        transition: DocumentStatusTransition,
        user_id: UUID | None = None,
    ) -> Document:
        """Transition document to a new status.

        Validates against template's status machine. Creates version + operation.

        Raises:
            DocumentNotFoundError: If document doesn't exist.
            InvalidStatusTransitionError: If the transition is not allowed.
        """
        document = await self.get(document_id, tenant_id)
        old_status = document.status
        new_status = transition.new_status

        # Validate transition if template has status machine
        if document.template and document.template.statuses:
            current_state = next(
                (s for s in document.template.statuses if s["key"] == old_status),
                None,
            )
            if current_state:
                allowed = current_state.get("transitions_to", [])
                if new_status not in allowed:
                    raise InvalidStatusTransitionError(
                        f"Cannot transition from '{old_status}' to '{new_status}'. "
                        f"Allowed: {allowed}"
                    )

        now = datetime.now(UTC)
        document.status = new_status
        new_version_num = document.version + 1
        document.version = new_version_num
        document.updated_at = now

        # Version snapshot
        version = DocumentVersion(
            document_id=document.id,
            version=new_version_num,
            fields_snapshot=dict(document.fields),
            status=new_status,
            change_description=f"Status: {old_status} → {new_status}"
            + (f" — {transition.comment}" if transition.comment else ""),
            changed_by=user_id,
            created_at=now,
        )
        self._session.add(version)

        # Operation record
        operation = DocumentOperation(
            document_id=document.id,
            version=new_version_num,
            op_type="status_change",
            op_data={
                "old_status": old_status,
                "new_status": new_status,
                "comment": transition.comment,
            },
            user_id=user_id,
            created_at=now,
        )
        self._session.add(operation)

        logger.info(
            "Document status transition: id=%s %s→%s",
            document.id,
            old_status,
            new_status,
        )

        await self._session.flush()
        return document

    async def soft_delete(self, document_id: UUID, tenant_id: UUID) -> Document:
        """Soft-delete a document (moves to Trash, recoverable for 30 days)."""
        document = await self.get(document_id, tenant_id)
        document.is_deleted = True
        document.deleted_at = datetime.now(UTC)
        document.updated_at = datetime.now(UTC)

        operation = DocumentOperation(
            document_id=document.id,
            version=document.version,
            op_type="delete",
            op_data={"method": "soft"},
            created_at=datetime.now(UTC),
        )
        self._session.add(operation)

        await self._session.flush()
        logger.info("Document soft-deleted: id=%s", document.id)
        return document

    async def restore(self, document_id: UUID, tenant_id: UUID) -> Document:
        """Restore a soft-deleted document from Trash."""
        document = await self._session.execute(
            select(Document).where(
                Document.id == document_id,
                Document.tenant_id == tenant_id,
                Document.is_deleted == True,  # noqa: E712
            )
        )

        document = document.scalar_one_or_none()
        if document is None:
            raise DocumentNotFoundError(f"Document {document_id} not found in trash")

        document.is_deleted = False
        document.deleted_at = None
        document.updated_at = datetime.now(UTC)

        operation = DocumentOperation(
            document_id=document.id,
            version=document.version,
            op_type="restore",
            op_data={"restored_at": datetime.now(UTC).isoformat()},
            created_at=datetime.now(UTC),
        )
        self._session.add(operation)

        await self._session.flush()
        logger.info("Document restored: id=%s", document.id)
        return document

    # ── Versions ────────────────────────────────────────────────

    async def get_versions(self, document_id: UUID, tenant_id: UUID) -> list[DocumentVersion]:
        """Get all versions for a document, newest first."""
        await self.get(document_id, tenant_id)  # Verify document exists
        result = await self._session.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version.desc())
        )
        return list(result.scalars().all())

    async def get_version(
        self, document_id: UUID, version: int, tenant_id: UUID
    ) -> DocumentVersion:
        """Get a specific version of a document."""
        await self.get(document_id, tenant_id)
        result = await self._session.execute(
            select(DocumentVersion).where(
                DocumentVersion.document_id == document_id,
                DocumentVersion.version == version,
            )
        )
        ver = result.scalar_one_or_none()
        if ver is None:
            raise ValueError(f"Version {version} not found for document {document_id}")
        return ver

    async def rollback_to_version(
        self, document_id: UUID, version: int, tenant_id: UUID, user_id: UUID | None = None
    ) -> Document:
        """Restore document state from a historical version snapshot."""
        target = await self.get_version(document_id, version, tenant_id)
        document = await self.get(document_id, tenant_id)

        update_data = DocumentUpdate(fields=dict(target.fields_snapshot))
        await self.update(document_id, tenant_id, update_data, user_id)

        # Add operation record for rollback
        operation = DocumentOperation(
            document_id=document.id,
            version=document.version,
            op_type="field_update",
            op_data={
                "action": "rollback",
                "from_version": document.version - 1,
                "to_version": version,
            },
            user_id=user_id,
            created_at=datetime.now(UTC),
        )
        self._session.add(operation)
        await self._session.flush()

        return document

    # ── Tags ────────────────────────────────────────────────────

    async def add_tag(self, document_id: UUID, tenant_id: UUID, tag_name: str) -> Document:
        """Add a tag to a document. Creates the tag if it doesn't exist."""
        document = await self.get(document_id, tenant_id)

        # Find or create tag
        result = await self._session.execute(
            select(Tag).where(Tag.tenant_id == tenant_id, Tag.name == tag_name)
        )
        tag = result.scalar_one_or_none()
        if tag is None:
            tag = Tag(tenant_id=tenant_id, name=tag_name, created_at=datetime.now(UTC))
            self._session.add(tag)
            await self._session.flush()

        # Check if already tagged
        existing = await self._session.execute(
            select(DocumentTag).where(
                DocumentTag.document_id == document_id, DocumentTag.tag_id == tag.id
            )
        )
        if existing.scalar_one_or_none() is None:
            doc_tag = DocumentTag(document_id=document_id, tag_id=tag.id)
            self._session.add(doc_tag)
            await self._session.flush()

        return document

    async def remove_tag(self, document_id: UUID, tenant_id: UUID, tag_name: str) -> Document:
        """Remove a tag from a document."""
        await self.get(document_id, tenant_id)

        result = await self._session.execute(
            select(Tag).where(Tag.tenant_id == tenant_id, Tag.name == tag_name)
        )
        tag = result.scalar_one_or_none()
        if tag:
            await self._session.execute(
                select(DocumentTag).where(
                    DocumentTag.document_id == document_id,
                    DocumentTag.tag_id == tag.id,
                )
            )
            # Delete the bridge row
            bridge = await self._session.execute(
                select(DocumentTag).where(
                    DocumentTag.document_id == document_id,
                    DocumentTag.tag_id == tag.id,
                )
            )
            bridge_row = bridge.scalar_one_or_none()
            if bridge_row:
                await self._session.delete(bridge_row)
                await self._session.flush()

        return await self.get(document_id, tenant_id)

    async def get_tags(self, document_id: UUID, tenant_id: UUID) -> list[Tag]:
        """Get all tags for a document."""
        await self.get(document_id, tenant_id)
        result = await self._session.execute(
            select(Tag).join(DocumentTag).where(DocumentTag.document_id == document_id)
        )
        return list(result.scalars().all())
