"""Master API router — includes all v1 sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.ai import router as ai_router
from app.api.v1.auth import router as auth_router
from app.api.v1.billing import router as billing_router
from app.api.v1.channels import router as channels_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.oauth import router as oauth_router
from app.api.v1.organisations import router as organisations_router
from app.api.v1.services import router as services_router
from app.api.v1.sso import router as sso_router
from app.api.v1.telegram_webhook import router as telegram_webhook_router
from app.api.v1.templates import router as templates_router
from app.api.v1.tenants import router as tenants_router
from app.api.v1.users import router as users_router

router = APIRouter(prefix="/v1")
router.include_router(health_router)
router.include_router(oauth_router)
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(organisations_router)
router.include_router(documents_router)
router.include_router(channels_router)
router.include_router(conversations_router)
router.include_router(ai_router, prefix="/ai")
router.include_router(services_router)
router.include_router(billing_router)
router.include_router(templates_router)
router.include_router(sso_router)
router.include_router(tenants_router)
router.include_router(telegram_webhook_router, prefix="/webhooks")
