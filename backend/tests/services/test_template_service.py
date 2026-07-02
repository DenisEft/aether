"""Tests for TemplateService."""

import pytest
from uuid import uuid4

from app.models.documents import Template
from app.services.template_service import (
    TemplateService,
    TemplateNotFoundError,
    SystemTemplateProtectedError,
    TemplateValidationError
)


@pytest.mark.asyncio
class TestTemplateServiceCreate:
    """Tests for TemplateService.create method."""

    async def test_create_template_success(self, template_service: TemplateService, test_template_data):
        """Test successful template creation."""
        template = await template_service.create(test_template_data)
        
        assert template.id is not None
        assert template.tenant_id == test_template_data["tenant_id"]
        assert template.name == test_template_data["name"]
        assert template.document_type == test_template_data["document_type"]
        assert template.fields == test_template_data["fields"]
        assert template.description == test_template_data["description"]
        assert template.icon == test_template_data["icon"]
        assert template.statuses == test_template_data["statuses"]
        assert template.is_system is False
        assert template.is_active is True

    async def test_create_template_with_default_statuses(self, template_service: TemplateService, test_template_data):
        """Test template creation with default statuses."""
        # Remove statuses from test data to test default
        test_data = test_template_data.copy()
        test_data["statuses"] = None
        
        template = await template_service.create(test_data)
        
        assert len(template.statuses) == 1
        assert template.statuses[0]["key"] == "new"
        assert template.statuses[0]["label"] == "Новый"
        assert template.statuses[0]["color"] == "#6b7280"
        assert template.statuses[0]["is_initial"] is True

    async def test_create_template_invalid_field_definition(self, template_service: TemplateService, test_template_data):
        """Test template creation with invalid field definition."""
        # Test missing key field
        test_data = test_template_data.copy()
        test_data["fields"] = [
            {
                "label": "Customer Name",  # Missing 'key'
                "type": "text"
            }
        ]
        
        with pytest.raises(TemplateValidationError, match="Each field must have a 'key' field"):
            await template_service.create(test_data)

        # Test missing label field
        test_data["fields"] = [
            {
                "key": "customer_name",
                "type": "text"  # Missing 'label'
            }
        ]
        
        with pytest.raises(TemplateValidationError, match="Each field must have a 'label' field"):
            await template_service.create(test_data)

        # Test missing type field
        test_data["fields"] = [
            {
                "key": "customer_name",
                "label": "Customer Name"  # Missing 'type'
            }
        ]
        
        with pytest.raises(TemplateValidationError, match="Each field must have a 'type' field"):
            await template_service.create(test_data)

    async def test_create_template_invalid_field_type(self, template_service: TemplateService, test_template_data):
        """Test template creation with invalid field definition."""
        test_data = test_template_data.copy()
        test_data["fields"] = [
            {
                "key": "customer_name",
                "label": "Customer Name",
                "type": "text",
                "required": True
            },
            "invalid_field"  # Invalid: should be dict
        ]
        
        with pytest.raises(TemplateValidationError, match="Each field must be a dictionary"):
            await template_service.create(test_data)


@pytest.mark.asyncio
class TestTemplateServiceGet:
    """Tests for TemplateService.get method."""

    async def test_get_template_success(self, template_service: TemplateService, test_template: Template):
        """Test successful template retrieval."""
        template = await template_service.get(test_template.id, test_template.tenant_id)
        
        assert template.id == test_template.id
        assert template.tenant_id == test_template.tenant_id
        assert template.name == test_template.name

    async def test_get_template_not_found(self, template_service: TemplateService):
        """Test template retrieval with non-existent ID."""
        with pytest.raises(TemplateNotFoundError):
            await template_service.get(uuid4(), uuid4())


@pytest.mark.asyncio
class TestTemplateServiceList:
    """Tests for TemplateService.list method."""

    async def test_list_templates_success(self, template_service: TemplateService, test_template: Template):
        """Test successful template listing."""
        templates, total = await template_service.list(test_template.tenant_id)
        
        assert total >= 1
        assert len(templates) >= 1
        assert templates[0].id == test_template.id

    async def test_list_templates_filter_by_document_type(self, template_service: TemplateService, test_template: Template):
        """Test template listing with document type filter."""
        templates, total = await template_service.list(
            test_template.tenant_id, 
            document_type=test_template.document_type
        )
        
        assert total >= 1
        assert len(templates) >= 1
        assert templates[0].document_type == test_template.document_type

    async def test_list_templates_filter_by_is_active(self, template_service: TemplateService, test_template: Template):
        """Test template listing with is_active filter."""
        templates, total = await template_service.list(
            test_template.tenant_id, 
            is_active=True
        )
        
        assert total >= 1
        assert len(templates) >= 1
        assert templates[0].is_active is True

    async def test_list_templates_search(self, template_service: TemplateService, test_template: Template):
        """Test template listing with search."""
        templates, total = await template_service.list(
            test_template.tenant_id, 
            search=test_template.name
        )
        
        assert total >= 1
        assert len(templates) >= 1
        assert templates[0].name == test_template.name


@pytest.mark.asyncio
class TestTemplateServiceUpdate:
    """Tests for TemplateService.update method."""

    async def test_update_template_success(self, template_service: TemplateService, test_template: Template):
        """Test successful template update."""
        update_data = {
            "name": "Updated Test Template",
            "description": "Updated description",
            "icon": "✏️"
        }
        
        updated_template = await template_service.update(
            test_template.id, 
            test_template.tenant_id, 
            update_data
        )
        
        assert updated_template.name == update_data["name"]
        assert updated_template.description == update_data["description"]
        assert updated_template.icon == update_data["icon"]

    async def test_update_template_fields(self, template_service: TemplateService, test_template: Template):
        """Test template update with field definitions."""
        update_data = {
            "fields": [
                {
                    "key": "new_field",
                    "label": "New Field",
                    "type": "text",
                    "required": True
                }
            ]
        }
        
        updated_template = await template_service.update(
            test_template.id, 
            test_template.tenant_id, 
            update_data
        )
        
        assert len(updated_template.fields) == 1
        assert updated_template.fields[0]["key"] == "new_field"

    async def test_update_template_invalid_field_definition(self, template_service: TemplateService, test_template: Template):
        """Test template update with invalid field definition."""
        update_data = {
            "fields": [
                {
                    "label": "Customer Name",  # Missing 'key'
                    "type": "text"
                }
            ]
        }
        
        with pytest.raises(TemplateValidationError, match="Each field must have a 'key' field"):
            await template_service.update(test_template.id, test_template.tenant_id, update_data)

    async def test_update_system_template(self, template_service: TemplateService, test_template: Template):
        """Test updating system template (should fail)."""
        # Make the template system
        test_template.is_system = True
        await template_service._session.flush()
        
        with pytest.raises(SystemTemplateProtectedError):
            await template_service.update(test_template.id, test_template.tenant_id, {"name": "should fail"})


@pytest.mark.asyncio
class TestTemplateServiceActivateDeactivate:
    """Tests for TemplateService.activate and deactivate methods."""

    async def test_activate_template(self, template_service: TemplateService, test_template: Template):
        """Test template activation."""
        # First deactivate
        await template_service.deactivate(test_template.id, test_template.tenant_id)
        
        # Then activate
        activated_template = await template_service.activate(test_template.id, test_template.tenant_id)
        
        assert activated_template.is_active is True

    async def test_deactivate_template(self, template_service: TemplateService, test_template: Template):
        """Test template deactivation."""
        deactivated_template = await template_service.deactivate(test_template.id, test_template.tenant_id)
        
        assert deactivated_template.is_active is False

    async def test_activate_system_template(self, template_service: TemplateService, test_template: Template):
        """Test activating system template (should fail)."""
        test_template.is_system = True
        await template_service._session.flush()
        
        with pytest.raises(SystemTemplateProtectedError):
            await template_service.activate(test_template.id, test_template.tenant_id)

    async def test_deactivate_system_template(self, template_service: TemplateService, test_template: Template):
        """Test deactivating system template (should fail)."""
        test_template.is_system = True
        await template_service._session.flush()
        
        with pytest.raises(SystemTemplateProtectedError):
            await template_service.deactivate(test_template.id, test_template.tenant_id)


@pytest.mark.asyncio
class TestTemplateServiceDelete:
    """Tests for TemplateService.delete method."""

    async def test_delete_template(self, template_service: TemplateService, test_template: Template):
        """Test template soft delete."""
        deleted_template = await template_service.delete(test_template.id, test_template.tenant_id)
        
        assert deleted_template.is_active is False

    async def test_delete_system_template(self, template_service: TemplateService, test_template: Template):
        """Test deleting system template (should fail)."""
        test_template.is_system = True
        await template_service._session.flush()
        
        with pytest.raises(SystemTemplateProtectedError):
            await template_service.delete(test_template.id, test_template.tenant_id)


@pytest.mark.asyncio
class TestTemplateServiceGetByType:
    """Tests for TemplateService.get_by_type method."""

    async def test_get_by_type_success(self, template_service: TemplateService, test_template: Template):
        """Test getting templates by document type."""
        templates = await template_service.get_by_type(
            test_template.tenant_id, 
            test_template.document_type
        )
        
        assert len(templates) >= 1
        assert templates[0].document_type == test_template.document_type
        assert templates[0].is_active is True


@pytest.mark.asyncio
class TestTemplateServiceValidateFields:
    """Tests for TemplateService.validate_fields method."""

    async def test_validate_fields_success(self, template_service: TemplateService, test_template: Template):
        """Test successful field validation."""
        document_fields = {
            "customer_name": "John Doe",
            "amount": 100.0
        }
        
        errors = template_service.validate_fields(test_template, document_fields)
        assert errors == []

    async def test_validate_fields_missing_required(self, template_service: TemplateService, test_template: Template):
        """Test field validation with missing required fields."""
        document_fields = {
            "amount": 100.0  # Missing required 'customer_name'
        }
        
        errors = template_service.validate_fields(test_template, document_fields)
        assert len(errors) == 1
        assert "Required field 'Customer Name' is missing" in errors[0]

    async def test_validate_fields_unknown_field(self, template_service: TemplateService, test_template: Template):
        """Test field validation with unknown field (should not fail but log)."""
        document_fields = {
            "customer_name": "John Doe",
            "unknown_field": "some value"
        }
        
        errors = template_service.validate_fields(test_template, document_fields)
        assert len(errors) == 1
        assert "Unknown field 'unknown_field'" in errors[0]


@pytest.mark.asyncio
class TestTemplateServiceGetStatusOptions:
    """Tests for TemplateService.get_status_options method."""

    async def test_get_status_options_success(self, template_service: TemplateService, test_template: Template):
        """Test getting status options."""
        status_options = template_service.get_status_options(test_template)
        
        assert len(status_options) == 1
        assert status_options[0]["key"] == "new"
        assert status_options[0]["label"] == "Новый"