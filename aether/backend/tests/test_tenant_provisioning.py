"""Tests for TenantProvisioningService."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from app.services.tenant_provisioning import TenantProvisioningService


@pytest.fixture
def mock_session():
    """Create a mock SQLAlchemy session."""
    return AsyncMock()


@pytest.fixture
def provisioning_service(mock_session):
    """Create a TenantProvisioningService instance."""
    return TenantProvisioningService(mock_session)


@pytest.mark.asyncio
async def test_provision_tenant_success(provisioning_service, mock_session):
    """Test successful tenant provisioning."""
    # Mock tenant data
    tenant_id = uuid4()
    
    # Mock the session execute and scalar_one_or_none to return a tenant
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = MagicMock()
    mock_session.execute.return_value = mock_result
    
    # Call the method
    result = await provisioning_service.provision_tenant(tenant_id)
    
    # Verify result
    assert result["status"] == "success"
    assert result["tenant_id"] == str(tenant_id)
    assert "provisioned_at" in result


@pytest.mark.asyncio
async def test_suspend_tenant_success(provisioning_service, mock_session):
    """Test successful tenant suspension."""
    tenant_id = uuid4()
    
    # Mock the session execute and scalar_one_or_none to return a tenant
    mock_result = MagicMock()
    mock_tenant = MagicMock()
    mock_tenant.status = "active"
    mock_result.scalar_one_or_none.return_value = mock_tenant
    mock_session.execute.return_value = mock_result
    
    # Call the method
    result = await provisioning_service.suspend_tenant(tenant_id, "Test suspension reason")
    
    # Verify result
    assert result["status"] == "success"
    assert result["tenant_id"] == str(tenant_id)
    assert "suspended_at" in result


@pytest.mark.asyncio
async def test_activate_tenant_success(provisioning_service, mock_session):
    """Test successful tenant activation."""
    tenant_id = uuid4()
    
    # Mock the session execute and scalar_one_or_none to return a tenant
    mock_result = MagicMock()
    mock_tenant = MagicMock()
    mock_tenant.status = "suspended"
    mock_result.scalar_one_or_none.return_value = mock_tenant
    mock_session.execute.return_value = mock_result
    
    # Call the method
    result = await provisioning_service.activate_tenant(tenant_id)
    
    # Verify result
    assert result["status"] == "success"
    assert result["tenant_id"] == str(tenant_id)
    assert "activated_at" in result


@pytest.mark.asyncio
async def test_delete_tenant_soft_success(provisioning_service, mock_session):
    """Test soft tenant deletion."""
    tenant_id = uuid4()
    
    # Mock the session execute and scalar_one_or_none to return a tenant
    mock_result = MagicMock()
    mock_tenant = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_tenant
    mock_session.execute.return_value = mock_result
    
    # Call the method
    result = await provisioning_service.delete_tenant(tenant_id, hard=False)
    
    # Verify result
    assert result["status"] == "success"
    assert result["tenant_id"] == str(tenant_id)
    assert "deleted_at" in result


@pytest.mark.asyncio
async def test_delete_tenant_hard_success(provisioning_service, mock_session):
    """Test hard tenant deletion."""
    tenant_id = uuid4()
    
    # Mock the session execute and scalar_one_or_none to return a tenant
    mock_result = MagicMock()
    mock_tenant = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_tenant
    mock_session.execute.return_value = mock_result
    
    # Call the method
    result = await provisioning_service.delete_tenant(tenant_id, hard=True)
    
    # Verify result
    assert result["status"] == "success"
    assert result["tenant_id"] == str(tenant_id)
    assert "deleted_at" in result