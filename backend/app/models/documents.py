"""Document core models for Aether.

The central entity of Aether is the Document — an AI-processed, template-driven
record created from incoming messages (Telegram, email, widget) or manual input.

Architecture:
    Document → fields JSONB (template-defined schema)
    Document → status (from template's status machine)
    Document → DocumentVersion (full snapshot on each save)
    Document → DocumentOperation (audit trail)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey, utcnow

# ── Document ────────────────────────────────────────────────────────────────


class Document(Base, UUIDPrimaryKey, TimestampMixin):
    """Core document entity — the heart of Aether.

    Every document is created from a template which defines:
    - fields schema (what data the document holds)
    - status machine (valid states and transitions)
    - AI parsing configuration (how to extract data from raw input)

    Documents support:
    - Multi-channel sources (Telegram, email, widget, API, manual)
    - AI extraction with confidence scores per field
    - Full version history (snapshots on every save)
    - Operational audit trail
    - Soft deletion with 30-day retention
    - Linking to related documents
    """

    __tablename__ = "documents"

    # ── Identity ──────────────────────────────────────────
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Document type key: order, invoice, request, act, waybill, etrn",
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("templates.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Current status from template's status machine",
    )
    title: Mapped[str | None] = mapped_column(String(500))
    number: Mapped[str | None] = mapped_column(
        String(100),
        comment="Human-readable number, auto-generated: ORD-2026-0056",
    )

    # ── Data ──────────────────────────────────────────────
    fields: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="All document fields as defined by template. Key: field key, Value: field value",
    )
    field_confidence: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Per-field AI extraction confidence scores: {field_key: 0.0-1.0}",
    )
    overall_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Average AI confidence across all fields (0.0-1.0)",
    )

    # ── Source ─────────────────────────────────────────────
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="manual",
        comment="Source channel: manual, telegram, email, widget, api, scan",
    )
    source_message_id: Mapped[str | None] = mapped_column(
        String(500),
        comment="External message ID from the source channel",
    )
    source_meta: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional source metadata (sender, channel info, raw text)",
    )

    # ── Relationships ─────────────────────────────────────
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisations.id", ondelete="SET NULL"), nullable=True,
    )
    creator_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    linked_document_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        JSONB,
        default=None,
        comment="Related document IDs (e.g., order linked to invoice)",
    )

    # ── Versioning ─────────────────────────────────────────
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # ── Soft Delete ────────────────────────────────────────
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Soft delete timestamp"
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Relationships ─────────────────────────────────────
    tenant: Mapped["Tenant"] = relationship(back_populates="documents")
    template: Mapped["Template | None"] = relationship(back_populates="documents")
    company: Mapped["Organisation | None"] = relationship()
    creator: Mapped["User | None"] = relationship()
    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document", order_by="DocumentVersion.version.desc()",
    )
    operations: Mapped[list["DocumentOperation"]] = relationship(
        back_populates="document", order_by="DocumentOperation.created_at.desc()",
    )
    tags: Mapped[list["DocumentTag"]] = relationship(back_populates="document")

    # ── Constraints ────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("tenant_id", "type", "number", name="uq_document_number"),
        {"comment": "Core document entity — AI-processed, template-driven records"},
    )


# ── Document Version ───────────────────────────────────────────────────────


class DocumentVersion(Base, UUIDPrimaryKey):
    """Full snapshot of a document at a specific point in time.

    Created automatically on every save. Enables:
    - Diff between any two versions
    - Rollback to any historical state
    - Audit trail of who changed what
    """

    __tablename__ = "document_versions"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    fields_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    change_description: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    document: Mapped["Document"] = relationship(back_populates="versions")

    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_doc_version"),
        {"comment": "Point-in-time snapshot of document state"},
    )


# ── Document Operation ─────────────────────────────────────────────────────


class DocumentOperation(Base, UUIDPrimaryKey):
    """Individual operation record — fine-grained audit trail.

    Every field change, status transition, file attachment, creation, and deletion
    is recorded as an operation. This enables:
    - Complete audit trail
    - Per-field change tracking
    - Activity log / timeline display
    """

    __tablename__ = "document_operations"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    op_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Operation type: field_update, status_change, file_attach, create, delete, restore",
    )
    op_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Operation details: {field: 'cargo', old: 'уголь', new: 'руда'} or {status: 'confirmed'}",
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    document: Mapped["Document"] = relationship(back_populates="operations")
    user: Mapped["User | None"] = relationship()

    __table_args__ = (
        {"comment": "Per-operation audit trail for document changes"},
    )


# ── Document Tag ───────────────────────────────────────────────────────────


class DocumentTag(Base, UUIDPrimaryKey):
    """User-defined tags for organizing documents.

    Tags bridge documents and the tags table. A document can have multiple tags.
    """

    __tablename__ = "document_tags"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False
    )

    document: Mapped["Document"] = relationship(back_populates="tags")
    tag: Mapped["Tag"] = relationship(back_populates="documents")

    __table_args__ = (
        UniqueConstraint("document_id", "tag_id", name="uq_doc_tag"),
        {"comment": "Many-to-many bridge between documents and tags"},
    )


# ── Tag ────────────────────────────────────────────────────────────────────


class Tag(Base, UUIDPrimaryKey):
    """User-defined tag for organizing documents.

    Tags are per-tenant and can be created/renamed/deleted by users.
    """

    __tablename__ = "tags"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str | None] = mapped_column(String(7), comment="Hex color: #FF5733")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    documents: Mapped[list["DocumentTag"]] = relationship(back_populates="tag")

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_tag_name"),
        {"comment": "User-defined document tags"},
    )


# ── Template ───────────────────────────────────────────────────────────────


class Template(Base, UUIDPrimaryKey, TimestampMixin):
    """Document template — defines the schema and behavior for a document type.

    Templates are the "rails" for AI:
    - fields: Defines what data to extract and how to display it
    - statuses: Defines the valid states and transitions
    - parsing_config: Defines how AI extracts data from raw text
    - pdf_template: HTML template for PDF generation
    """

    __tablename__ = "templates"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        comment="NULL for system templates (library)",
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    document_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Links to documents.type"
    )
    icon: Mapped[str | None] = mapped_column(String(10), comment="Emoji: 📦, 💰, 📝")
    fields: Mapped[list[dict]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Array of field definitions: {key, label, type, required, order, ai_keywords, ...}",
    )
    statuses: Mapped[list[dict]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Status machine: [{key, label, color, is_initial, is_final, transitions_to}, ...]",
    )
    parsing_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="AI parsing configuration: {ai_prompt, field_mapping, confidence_threshold, auto_confirm_fields}",
    )
    pdf_template: Mapped[str | None] = mapped_column(
        Text, comment="HTML template for PDF generation (Jinja2)"
    )
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, comment="System template, cannot be deleted")
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, comment="Available in template library")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    documents: Mapped[list["Document"]] = relationship(back_populates="template")

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_template_name"),
        {"comment": "Document template — defines schema, status machine, and AI parsing config"},
    )
