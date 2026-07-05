"""add_document_models

Revision ID: b725e5bb88e9
Revises: 2e83f710a1b1
Create Date: 2026-07-02 00:43:46.751588
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b725e5bb88e9"
down_revision: Union[str, Sequence[str], None] = "2e83f710a1b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add document models: documents, templates, tags, versioning, operations."""

    # ── Tags ──────────────────────────────────────────────────
    op.create_table(
        "tags",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=True, comment="Hex color: #FF5733"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_tag_name"),
        comment="User-defined document tags",
    )
    op.create_index(op.f("ix_tags_tenant_id"), "tags", ["tenant_id"], unique=False)

    # ── Templates ─────────────────────────────────────────────
    op.create_table(
        "templates",
        sa.Column(
            "tenant_id",
            sa.UUID(),
            nullable=True,
            comment="NULL for system templates (library)",
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("document_type", sa.String(length=50), nullable=False, comment="Links to documents.type"),
        sa.Column("icon", sa.String(length=10), nullable=True, comment="Emoji icon"),
        sa.Column(
            "fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Array of field definitions",
        ),
        sa.Column(
            "statuses",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Status machine definition",
        ),
        sa.Column(
            "parsing_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="AI parsing configuration",
        ),
        sa.Column("pdf_template", sa.Text(), nullable=True, comment="HTML template for PDF (Jinja2)"),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false"), comment="System template, cannot be deleted"),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("false"), comment="Available in template library"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_template_name"),
        comment="Document template — defines schema, status machine, and AI parsing config",
    )

    # ── Documents (core) ──────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False, comment="Document type key"),
        sa.Column("template_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, comment="Current status from template's status machine"),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("number", sa.String(length=100), nullable=True, comment="Human-readable number: ORD-2026-0056"),
        sa.Column(
            "fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Document fields defined by template",
        ),
        sa.Column(
            "field_confidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Per-field AI confidence scores",
        ),
        sa.Column("overall_confidence", sa.Float(), nullable=True, comment="Average AI confidence"),
        sa.Column("source", sa.String(length=50), nullable=False, server_default=sa.text("'manual'"), comment="Source channel"),
        sa.Column("source_message_id", sa.String(length=500), nullable=True, comment="External message ID"),
        sa.Column(
            "source_meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Additional source metadata",
        ),
        sa.Column("company_id", sa.UUID(), nullable=True),
        sa.Column("creator_id", sa.UUID(), nullable=True),
        sa.Column(
            "linked_document_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Related document IDs",
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True, comment="Soft delete timestamp"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["organisations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["template_id"], ["templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "type", "number", name="uq_document_number"),
        comment="Core document entity — AI-processed, template-driven records",
    )
    op.create_index(op.f("ix_documents_tenant_id"), "documents", ["tenant_id"], unique=False)
    op.create_index("idx_documents_tenant_status", "documents", ["tenant_id", "status"])
    op.create_index("idx_documents_tenant_type", "documents", ["tenant_id", "type"])
    op.create_index("idx_documents_tenant_created", "documents", ["tenant_id", sa.text("created_at DESC")])
    op.create_index("idx_documents_fields_gin", "documents", ["fields"], postgresql_using="gin")
    op.create_index("idx_documents_deleted", "documents", ["deleted_at"], postgresql_where=sa.text("deleted_at IS NOT NULL"))

    # ── Document Versions ─────────────────────────────────────
    op.create_table(
        "document_versions",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("fields_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("change_description", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "version", name="uq_doc_version"),
        comment="Point-in-time snapshot of document state",
    )

    # ── Document Operations ───────────────────────────────────
    op.create_table(
        "document_operations",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "op_type",
            sa.String(length=50),
            nullable=False,
            comment="field_update, status_change, file_attach, create, delete, restore",
        ),
        sa.Column("op_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        comment="Per-operation audit trail for document changes",
    )
    op.create_index(
        op.f("ix_document_operations_document_id"),
        "document_operations",
        ["document_id", "created_at"],
        unique=False,
    )

    # ── Document Tags (bridge) ─────────────────────────────────
    op.create_table(
        "document_tags",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("tag_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "tag_id", name="uq_doc_tag"),
        comment="Many-to-many bridge between documents and tags",
    )


def downgrade() -> None:
    """Remove document models."""
    op.drop_table("document_tags")
    op.drop_index(op.f("ix_document_operations_document_id"), table_name="document_operations")
    op.drop_table("document_operations")
    op.drop_table("document_versions")
    op.drop_index("idx_documents_deleted", table_name="documents")
    op.drop_index("idx_documents_fields_gin", table_name="documents", postgresql_using="gin")
    op.drop_index("idx_documents_tenant_created", table_name="documents")
    op.drop_index("idx_documents_tenant_type", table_name="documents")
    op.drop_index("idx_documents_tenant_status", table_name="documents")
    op.drop_index(op.f("ix_documents_tenant_id"), table_name="documents")
    op.drop_table("documents")
    op.drop_table("templates")
    op.drop_index(op.f("ix_tags_tenant_id"), table_name="tags")
    op.drop_table("tags")
