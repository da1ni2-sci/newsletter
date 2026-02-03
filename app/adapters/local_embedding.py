from typing import List
from langchain_ollama import OllamaEmbeddings
from app.core.interfaces import EmbeddingProvider

class LocalEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str = "qwen3-embedding:latest", base_url: str = "http://localhost:11434"):
        """
        Switched to Ollama for embeddings to support specialized models like qwen3-embedding.
        """
        self.client = OllamaEmbeddings(
            model=model_name,
            base_url=base_url
        )

    async def embed_query(self, text: str) -> List[float]:
        # LangChain OllamaEmbeddings.embed_query is synchronous by default in many versions, 
        # but langchain_ollama provides an async version.
        return await self.client.aembed_query(text)

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return await self.client.aembed_documents(texts)
