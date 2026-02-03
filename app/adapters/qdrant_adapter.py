from typing import List, Dict, Any
from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.http import models
from app.core.interfaces import VectorStoreProvider
import os

class QdrantAdapter(VectorStoreProvider):
    def __init__(self, host: str = "localhost", port: int = 6333):
        self.client = AsyncQdrantClient(host=host, port=port)

    async def create_collection(self, collection_name: str, vector_size: int):
        # Helper to ensure collection exists
        collections = await self.client.get_collections()
        exists = any(c.name == collection_name for c in collections.collections)
        
        if not exists:
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
            )

    async def upsert(self, collection_name: str, points: List[Dict[str, Any]]):
        # points expected in a format compatible with Qdrant
        await self.client.upsert(
            collection_name=collection_name,
            points=points
        )

    async def search(self, collection_name: str, query_vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        hits = await self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit
        )
        return [{"id": hit.id, "payload": hit.payload, "score": hit.score} for hit in hits]
