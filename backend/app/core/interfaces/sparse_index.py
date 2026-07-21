from abc import ABC, abstractmethod
from typing import List, Optional

from app.core.entities.document import DocumentChunk


class ISparseIndex(ABC):
    """Keyword/BM25-style sparse retrieval, scoped per user. Swappable:
    pickle+rank_bm25 today; Elasticsearch/OpenSearch tomorrow (per the
    original project's own TODO list) without touching RetrievalService."""

    @abstractmethod
    def add_documents(self, user_id: str, chunks: List[DocumentChunk]) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(self, user_id: str, query: str, top_k: int, file_ids: Optional[List[str]] = None) -> List[DocumentChunk]:
        raise NotImplementedError

    @abstractmethod
    def remove_file(self, user_id: str, file_id: str) -> None:
        raise NotImplementedError
