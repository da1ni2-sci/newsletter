from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class LLMProvider(ABC):
    """Abstract interface for LLM providers (DeepSeek, OpenAI, Ollama, etc.)"""
    @abstractmethod
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        pass

class EmbeddingProvider(ABC):
    """Abstract interface for Embedding models (Voyage, OpenAI, BGE-M3 via FastEmbed)"""
    @abstractmethod
    async def embed_query(self, text: str) -> List[float]:
        pass

    @abstractmethod
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        pass

class VectorStoreProvider(ABC):
    """Abstract interface for Vector Databases (Qdrant, etc.)"""
    @abstractmethod
    async def upsert(self, collection_name: str, points: List[Dict[str, Any]]):
        pass

    @abstractmethod
    async def search(self, collection_name: str, query_vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        pass

class IngestionStrategy(ABC):
    """Strategy for different data sources (RSS, GitHub, Papers)"""
    @abstractmethod
    async def fetch(self, source_url: str) -> List[Dict[str, Any]]:
        pass
