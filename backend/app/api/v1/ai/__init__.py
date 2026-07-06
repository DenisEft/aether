"""AI module routers."""

from fastapi import APIRouter

from .drivers import router as drivers_router
from .entities import router as entities_router
from .inference import router as inference_router
from .intents import router as intents_router
from .knowledge_bases import router as knowledge_bases_router
from .models import router as models_router

# Include all sub-routers in the main AI router
router = APIRouter(tags=["ai"])

router.include_router(intents_router)
router.include_router(entities_router)
router.include_router(models_router)
router.include_router(drivers_router)
router.include_router(knowledge_bases_router)
router.include_router(inference_router)
