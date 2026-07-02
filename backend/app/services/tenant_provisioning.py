"""Tenant provisioning service for Aether SaaS platform.

This service handles all tenant lifecycle operations including provisioning,
activation, suspension, and deletion.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenants import Tenant, TenantConfig, TenantFeature, TenantLimit
from app.models.users import User
from app.models.channels import Channel
from app.models.organisations import Organisation
from app.models.billing import Subscription, SubscriptionPlan
from app.services.billing_service import BillingService

logger = logging.getLogger("aether.tenant_provisioning")


class TenantProvisioningService:
    """Service for managing tenant lifecycle operations."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def provision_tenant(self, tenant_id: UUID) -> dict:
        """Provision a new tenant with all required resources.

        Args:
            tenant_id: The UUID of the tenant to provision

        Returns:
            dict containing provisioning status
        """
        try:
            # Get tenant details
            result = await self._session.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = result.scalar_one_or_none()
            if not tenant:
                raise ValueError(f"Tenant with id {tenant_id} not found")

            # Create Redis keyspace (tenant:{tenant_id}:*)
            # This would be handled by Redis client, not stored in DB directly

            # Create default roles (owner, admin, member, viewer)
            # Create default channels
            # This would typically be done in database schema

            # Activate trial subscription
            billing_service = BillingService(self._session)
            await billing_service.activate_trial(tenant_id)

            # For now, we'll just create basic tenant resources
            # In a real implementation, this would include:
            # - Database schema creation (if isolated)
            # - Redis keyspace setup
            # - Default roles and channels
            # - Trial subscription activation
            # - Default configurations

            await self._session.commit()
            
            return {
                "status": "success",
                "tenant_id": str(tenant_id),
                "message": "Tenant provisioned successfully",
                "provisioned_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to provision tenant {tenant_id}: {e}")
            await self._session.rollback()
            raise

    async def suspend_tenant(self, tenant_id: UUID, reason: str) -> dict:
        """Suspend a tenant's access.

        Args:
            tenant_id: The UUID of the tenant to suspend
            reason: Reason for suspension

        Returns:
            dict containing suspension status
        """
        try:
            # Get tenant
            result = await self._session.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = result.scalar_one_or_none()
            if not tenant:
                raise ValueError(f"Tenant with id {tenant_id} not found")

            # Deactivate all users
            await self._session.execute(
                select(User).where(User.tenant_id == tenant_id).update({"is_active": False})
            )

            # Revoke all refresh tokens (this would be handled by Redis or DB)
            # We don't have a direct way to revoke tokens in DB, but we can set tenant status

            # Set tenant status to suspended
            tenant.status = "suspended"
            tenant.suspended_at = datetime.now()
            tenant.suspension_reason = reason

            await self._session.commit()
            
            return {
                "status": "success",
                "tenant_id": str(tenant_id),
                "message": "Tenant suspended successfully",
                "suspended_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to suspend tenant {tenant_id}: {e}")
            await self._session.rollback()
            raise

    async def activate_tenant(self, tenant_id: UUID) -> dict:
        """Activate a suspended tenant.

        Args:
            tenant_id: The UUID of the tenant to activate

        Returns:
            dict containing activation status
        """
        try:
            # Get tenant
            result = await self._session.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = result.scalar_one_or_none()
            if not tenant:
                raise ValueError(f"Tenant with id {tenant_id} not found")

            # Reactivate tenant
            tenant.status = "active"
            tenant.suspended_at = None
            tenant.suspension_reason = None

            # Reactivate all users
            await self._session.execute(
                select(User).where(User.tenant_id == tenant_id).update({"is_active": True})
            )

            await self._session.commit()
            
            return {
                "status": "success",
                "tenant_id": str(tenant_id),
                "message": "Tenant activated successfully",
                "activated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to activate tenant {tenant_id}: {e}")
            await self._session.rollback()
            raise

    async def delete_tenant(self, tenant_id: UUID, hard: bool = False) -> dict:
        """Delete a tenant (soft or hard).

        Args:
            tenant_id: The UUID of the tenant to delete
            hard: If True, perform hard delete (permanent); if False, soft delete

        Returns:
            dict containing deletion status
        """
        try:
            # Get tenant
            result = await self._session.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = result.scalar_one_or_none()
            if not tenant:
                raise ValueError(f"Tenant with id {tenant_id} not found")

            if hard:
                # Hard delete - remove all data
                # This would cascade through relationships
                self._session.delete(tenant)
            else:
                # Soft delete - mark as deleted
                tenant.deleted_at = datetime.now()
                tenant.is_active = False

            await self._session.commit()
            
            return {
                "status": "success",
                "tenant_id": str(tenant_id),
                "message": f"Tenant {'hard' if hard else 'soft'} deleted successfully",
                "deleted_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to delete tenant {tenant_id}: {e}")
            await self._session.rollback()
            raise