from abc import ABC, abstractmethod
from typing import List, Optional

from app.core.entities.document import DocumentChunk


class IVectorStore(ABC):
    """Dense vector persistence + similarity search, scoped per tenant.
    Swappable: Qdrant today; Pinecone/Weaviate/pgvector tomorrow."""

    @abstractmethod
    def upsert(
        self,
        chunks: List[DocumentChunk],
        vectors: List[List[float]],
        user_id: str,
        session_id: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query_vector: List[float],
        user_id: str,
        top_k: int,
        file_ids: Optional[List[str]] = None,
    ) -> List[DocumentChunk]:
        raise NotImplementedError

    @abstractmethod
    def delete_session(self, user_id: str, session_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete_file(self, user_id: str, file_id: str) -> None:
        raise NotImplementedError
