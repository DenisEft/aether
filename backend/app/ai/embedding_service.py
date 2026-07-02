"""Embedding service for vector operations."""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional, Dict, Any

from .drivers.base import BaseDriver, EmbeddingRequest, EmbeddingResponse
from .inference_pool import InferencePool

logger = logging.getLogger("aether.ai.embedding_service")


class EmbeddingService:
    """Service for managing embeddings with Qdrant-compatible interface."""

    def __init__(self, pool: InferencePool):
        self.pool = pool
        self._lock = asyncio.Lock()

    async def embed_texts(self, texts: List[str], 
                       model_id: Optional[str] = None,
                       tenant_id: Optional[str] = None) -> EmbeddingResponse:
        """Generate embeddings for a list of texts."""
        # Create embedding request
        request = EmbeddingRequest(
            texts=texts,
            tenant_id=tenant_id,
            model=model_id
        )
        
        # Select driver with embedding capability
        driver = self._select_embedding_driver(model_id)
        if not driver:
            raise RuntimeError("No driver available with embedding capability")
            
        # Generate embeddings
        try:
            response = await driver.embed(request)
            return response
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise

    async def index_documents(self, documents: List[Dict[str, Any]], 
                            collection_name: str,
                            model_id: Optional[str] = None,
                            tenant_id: Optional[str] = None):
        """Index documents into a collection."""
        # This would typically involve:
        # 1. Embedding the documents
        # 2. Chunking if needed
        # 3. Storing in Qdrant or similar vector DB
        raise NotImplementedError("Indexing functionality not implemented yet")

    async def search(self, query_text: str, 
                    collection_name: str,
                    limit: int = 10,
                    tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for similar documents in a collection."""
        # This would typically involve:
        # 1. Embedding the query
        # 2. Searching in Qdrant or similar vector DB
        # 3. Returning top matches
        raise NotImplementedError("Search functionality not implemented yet")

    async def delete_collection(self, collection_name: str, 
                             tenant_id: Optional[str] = None):
        """Delete a collection."""
        # This would remove the collection from vector DB
        raise NotImplementedError("Delete collection functionality not implemented yet")

    def _select_embedding_driver(self, model_id: Optional[str]) -> Optional[BaseDriver]:
        """Select a driver that supports embedding capability."""
        # First try to find a driver that supports embedding and matches the model
        if model_id:
            driver = self.pool.get_driver_for_model(model_id)
            if driver and "embedding" in [cap.value for cap in driver.capabilities()]:
                return driver
                
        # If no specific model or no driver with embedding, 
        # try to find any driver with embedding capability
        for driver in self.pool.get_all_drivers():
            if "embedding" in [cap.value for cap in driver.capabilities()]:
                return driver
                
        return None