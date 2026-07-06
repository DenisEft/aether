"""Template service — business logic for template CRUD and management.

All template operations go through this service. API routers delegate here.
No business logic lives in routers — they only handle HTTP concerns.

Design principles:
- All operations are scoped to tenant (except system templates)
- Templates are validated against their schema before creation/update
- Status transitions are validated against the template's status machine
- Soft delete only; hard delete requires explicit flag.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.documents import Template

logger = logging.getLogger(__name__)


# ── Errors ────────────────────────────────────────────────────


class TemplateNotFoundError(Exception):
    """Raised when a template is not found."""


class SystemTemplateProtectedError(Exception):
    """Raised when trying to modify or delete a system template."""


class TemplateValidationError(Exception):
    """Raised when template data fails validation."""


# ── Transport dataclasses ─────────────────────────────────────


@dataclass
class TemplateCreate:
    """Input for creating a template."""

    tenant_id: UUID | None
    name: str
    document_type: str
    fields: list[dict[str, Any]]
    description: str | None = None
    icon: str | None = None
    statuses: list[dict[str, Any]] | None = None
    parsing_config: dict[str, Any] | None = None
    pdf_template: str | None = None
    is_public: bool = False
    is_system: bool = False


@dataclass
class TemplateUpdate:
    """Input for updating a template. All fields optional for partial update."""

    name: str | None = None
    description: str | None = None
    icon: str | None = None
    fields: list[dict[str, Any]] | None = None
    statuses: list[dict[str, Any]] | None = None
    parsing_config: dict[str, Any] | None = None
    pdf_template: str | None = None
    is_public: bool | None = None
    is_active: bool | None = None


# ── Service ───────────────────────────────────────────────────


class TemplateService:
    """Business logic for template management.

    All template operations go through this service.
    API routers delegate here — no business logic in routers.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    # ── Helpers ────────────────────────────────────────────────

    @staticmethod
    def _get_value(data: Any, key: str) -> Any:
        """Get value from data whether it's a dict or dataclass."""
        if isinstance(data, dict):
            return data.get(key)
        return getattr(data, key, None)

    @staticmethod
    def _validate_field_definitions(fields: list[dict]) -> None:
        """Validate that each field definition has required keys."""
        for field in fields:
            if not isinstance(field, dict):
                raise TemplateValidationError("Each field must be a dictionary")
            if "key" not in field:
                raise TemplateValidationError("Each field must have a 'key' field")
            if "label" not in field:
                raise TemplateValidationError("Each field must have a 'label' field")
            if "type" not in field:
                raise TemplateValidationError("Each field must have a 'type' field")

    # ── CRUD ───────────────────────────────────────────────────

    async def create(self, data: TemplateCreate | dict[str, Any]) -> Template:
        """Create a new template.

        Args:
            data: TemplateCreate dataclass or dict with create fields.

        Returns:
            The newly created Template.

        Raises:
            TemplateValidationError: If field definitions are invalid.
        """
        # Resolve data whether it's a dataclass or dict
        tenant_id = self._get_value(data, "tenant_id")
        name = self._get_value(data, "name")
        description = self._get_value(data, "description")
        document_type = self._get_value(data, "document_type")
        icon = self._get_value(data, "icon")
        fields = self._get_value(data, "fields")
        statuses_raw = self._get_value(data, "statuses")
        parsing_config = self._get_value(data, "parsing_config")
        pdf_template = self._get_value(data, "pdf_template")
        is_public = self._get_value(data, "is_public") or False
        is_system = self._get_value(data, "is_system") or False

        # Validate field definitions
        self._validate_field_definitions(fields)

        # Set default statuses if not provided
        statuses = statuses_raw or [
            {"key": "new", "label": "Новый", "color": "#6b7280", "is_initial": True}
        ]

        template = Template(
            id=uuid4(),
            tenant_id=tenant_id,
            name=name,
            description=description,
            document_type=document_type,
            icon=icon,
            fields=fields,
            statuses=statuses,
            parsing_config=parsing_config or {},
            pdf_template=pdf_template,
            is_system=is_system,
            is_public=is_public,
            is_active=True,
        )

        self._session.add(template)
        await self._session.flush()
        logger.info(
            "Template created: id=%s tenant=%s name=%s",
            template.id,
            template.tenant_id,
            template.name,
        )
        return template

    async def get(self, template_id: UUID, tenant_id: UUID | None) -> Template:
        """Get a template by ID.

        Args:
            template_id: Template ID.
            tenant_id: Tenant ID (None for system templates).

        Returns:
            The Template.

        Raises:
            TemplateNotFoundError: If template doesn't exist.
        """
        result = await self._session.execute(select(Template).where(Template.id == template_id))
        template = result.scalar_one_or_none()
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        return template

    async def list(
        self,
        tenant_id: UUID | None,
        *,
        document_type: str | None = None,
        is_active: bool | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Template], int]:
        """List templates for a tenant plus system templates.

        Args:
            tenant_id: Tenant ID (includes system templates with tenant_id=None).
            document_type: Filter by document type.
            is_active: Filter by active status.
            search: Search by name or description.
            offset: Pagination offset.
            limit: Max results (capped at 100).

        Returns:
            Tuple of (items, total_count).
        """
        limit = min(limit, 100)

        # Base query: tenant-specific OR system templates
        conditions = [
            Template.is_active == True,
        ]
        if tenant_id is not None:
            conditions.append((Template.tenant_id == tenant_id) | (Template.tenant_id == None))
        if document_type:
            conditions.append(Template.document_type == document_type)
        if is_active is not None:
            conditions.append(Template.is_active == is_active)
        if search:
            conditions.append(
                (Template.name.ilike(f"%{search}%")) | (Template.description.ilike(f"%{search}%"))
            )

        # Total count
        count_query = select(func.count()).select_from(Template).where(*conditions)
        total_result = await self._session.execute(count_query)
        total = total_result.scalar_one()

        # Items
        items_query = (
            select(Template)
            .where(*conditions)
            .order_by(Template.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(items_query)
        items = result.scalars().all()

        return list(items), total

    async def update(
        self,
        template_id: UUID,
        tenant_id: UUID | None,
        data: TemplateUpdate | dict[str, Any],
    ) -> Template:
        """Update an existing template.

        Accepts both TemplateUpdate dataclass and plain dict.

        Args:
            template_id: Template ID to update.
            tenant_id: Tenant ID to scope the update.
            data: TemplateUpdate or dict with update fields.

        Returns:
            The updated Template.

        Raises:
            TemplateNotFoundError: If template doesn't exist.
            SystemTemplateProtectedError: If template is system.
            TemplateValidationError: If field definitions are invalid.
        """
        template = await self.get(template_id, tenant_id)
        if template.is_system:
            raise SystemTemplateProtectedError("System templates cannot be modified")

        # Update fields (duck-typing: dict or dataclass)
        new_name = self._get_value(data, "name")
        if new_name is not None:
            template.name = new_name
        new_description = self._get_value(data, "description")
        if new_description is not None:
            template.description = new_description
        new_icon = self._get_value(data, "icon")
        if new_icon is not None:
            template.icon = new_icon
        new_fields = self._get_value(data, "fields")
        if new_fields is not None:
            self._validate_field_definitions(new_fields)
            template.fields = new_fields
        new_statuses = self._get_value(data, "statuses")
        if new_statuses is not None:
            template.statuses = new_statuses
        new_parsing = self._get_value(data, "parsing_config")
        if new_parsing is not None:
            template.parsing_config = new_parsing
        new_pdf = self._get_value(data, "pdf_template")
        if new_pdf is not None:
            template.pdf_template = new_pdf
        new_public = self._get_value(data, "is_public")
        if new_public is not None:
            template.is_public = new_public
        new_active = self._get_value(data, "is_active")
        if new_active is not None:
            template.is_active = new_active

        await self._session.flush()
        logger.info(
            "Template updated: id=%s tenant=%s name=%s",
            template.id,
            template.tenant_id,
            template.name,
        )
        return template

    # ── Lifecycle ──────────────────────────────────────────────

    async def activate(self, template_id: UUID, tenant_id: UUID | None) -> Template:
        """Activate a template (set is_active=True).

        Raises:
            SystemTemplateProtectedError: If template is a system template.
        """
        template = await self.get(template_id, tenant_id)
        if template.is_system:
            raise SystemTemplateProtectedError("System templates cannot be modified")
        template.is_active = True
        await self._session.flush()
        logger.info("Template activated: id=%s", template.id)
        return template

    async def deactivate(self, template_id: UUID, tenant_id: UUID | None) -> Template:
        """Deactivate a template (set is_active=False).

        Raises:
            SystemTemplateProtectedError: If template is a system template.
        """
        template = await self.get(template_id, tenant_id)
        if template.is_system:
            raise SystemTemplateProtectedError("System templates cannot be modified")
        template.is_active = False
        await self._session.flush()
        logger.info("Template deactivated: id=%s", template.id)
        return template

    async def delete(self, template_id: UUID, tenant_id: UUID | None) -> Template:
        """Soft-delete a template (set is_active=False).

        System templates cannot be deleted.

        Returns:
            The deactivated Template.

        Raises:
            SystemTemplateProtectedError: If template is a system template.
        """
        template = await self.get(template_id, tenant_id)
        if template.is_system:
            raise SystemTemplateProtectedError("System templates cannot be deleted")
        template.is_active = False
        await self._session.flush()
        logger.info(
            "Template deleted: id=%s tenant=%s name=%s",
            template.id,
            template.tenant_id,
            template.name,
        )
        return template

    # ── Queries ────────────────────────────────────────────────

    async def get_by_type(self, tenant_id: UUID | None, document_type: str) -> list[Template]:
        """Get active templates for a document type (tenant + system)."""
        result = await self._session.execute(
            select(Template).where(
                (Template.tenant_id == tenant_id) | (Template.tenant_id == None),
                Template.document_type == document_type,
                Template.is_active == True,
            )
        )
        return list(result.scalars().all())

    # ── Validation ─────────────────────────────────────────────

    def validate_fields(self, template: Template, document_fields: dict[str, Any]) -> list[str]:
        """Validate document fields against template field definitions.

        Args:
            template: The template to validate against.
            document_fields: The document fields to validate.

        Returns:
            List of error messages (empty if valid).
        """
        errors: list[str] = []
        for field_def in template.fields:
            key = field_def.get("key")
            label = field_def.get("label", key)
            required = field_def.get("required", False)

            if required and (key not in document_fields or document_fields[key] is None):
                errors.append(f"Required field '{label}' is missing")
                continue

            if key in document_fields and document_fields[key] is not None:
                field_type = field_def.get("type", "text")
                value = document_fields[key]
                if field_type == "number" and not isinstance(value, (int, float)):
                    errors.append(f"Field '{label}' must be a number")
                elif field_type == "boolean" and not isinstance(value, bool):
                    errors.append(f"Field '{label}' must be a boolean")

        # Check for unknown fields
        known_keys = {fd["key"] for fd in template.fields}
        for key in document_fields:
            if key not in known_keys:
                errors.append(f"Unknown field '{key}'")

        return errors

    def get_status_options(self, template: Template) -> list[dict[str, Any]]:
        """Get available status options from template's status machine.

        Args:
            template: The template.

        Returns:
            List of status option dicts: {key, label, color, is_initial, transitions_to}.
        """
        return template.statuses or []
