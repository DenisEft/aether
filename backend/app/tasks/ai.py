"""Background AI tasks (queue: ai)."""

from __future__ import annotations

import logging

from app.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(bind=True, queue="ai", max_retries=0, soft_time_limit=30, time_limit=60, acks_late=True)
def process_intent(self, tenant_id: str, message_text: str, conversation_id: str | None = None) -> dict:
    """Classify intent and extract entities from a user message.

    Called after a message arrives through a channel.
    Uses AI driver pool for inference.
    Returns intent classification + extracted entities.
    """
    logger.info("process_intent: tenant=%s, conv=%s", tenant_id, conversation_id)
    # Stage 4: connect to AI driver pool
    return {"intent": "unknown", "entities": {}, "confidence": 0.0}


@celery.task(bind=True, queue="ai", max_retries=0, soft_time_limit=60, time_limit=120, acks_late=True)
def generate_response(
    self,
    tenant_id: str,
    conversation_id: str,
    intent: str,
    entities: dict | None = None,
    history: list | None = None,
) -> dict:
    """Generate an AI response for a conversation.

    Uses prompt templates + AI driver pool.
    Returns generated response text.
    """
    logger.info("generate_response: tenant=%s, conv=%s, intent=%s", tenant_id, conversation_id, intent)
    # Stage 4: connect to AI driver pool
    return {"text": "", "model": "default", "tokens_used": 0}


@celery.task(bind=True, queue="ai", max_retries=2, soft_time_limit=120, time_limit=300, acks_late=True)
def index_document(self, document_id: str) -> dict:
    """Index a knowledge document into the vector store (Qdrant).

    Steps: chunk document, generate embeddings, upsert vectors.
    Returns chunk_count + vector_dim.
    """
    logger.info("index_document: doc=%s", document_id)
    # Stage 4: connect to embedding model + Qdrant
    return {"chunk_count": 0, "vector_dim": 0}
