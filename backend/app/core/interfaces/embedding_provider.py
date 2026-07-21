from abc import ABC, abstractmethod
from typing import List


class IEmbeddingProvider(ABC):
    """Turns text into dense vectors. Swappable: HuggingFace today,
    OpenAI/Cohere/etc tomorrow, with zero changes to any caller."""

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        raise NotImplementedError
