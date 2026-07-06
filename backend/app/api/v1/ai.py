"""AI Core endpoints: intents, entities, AI models, drivers, knowledge bases."""

# Import the sub-routers and include them
from .ai import router as ai_router

# This file now just serves as a re-export of the main AI router
# All functionality has been moved to the submodules in backend/app/api/v1/ai/
router = ai_router
