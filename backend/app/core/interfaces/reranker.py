from abc import ABC, abstractmethod
from typing import List

from app.core.entities.document import DocumentChunk


class IReranker(ABC):
    """Re-scores a candidate set against a query and returns the top-N,
    most-relevant-first. Swappable: local CrossEncoder today; a hosted
    reranking API tomorrow."""

    @abstractmethod
    def rerank(self, query: str, candidates: List[DocumentChunk], top_n: int) -> List[DocumentChunk]:
        raise NotImplementedError
