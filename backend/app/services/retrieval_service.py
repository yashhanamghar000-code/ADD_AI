"""
Use case: hybrid (dense + sparse) retrieval and reranking for one query,
scoped to a tenant. Depends only on IEmbeddingProvider, IVectorStore,
ISparseIndex, IReranker — every one of those is swappable independently.
"""
from typing import List, Optional

from app.core.entities.document import DocumentChunk
from app.core.interfaces.embedding_provider import IEmbeddingProvider
from app.core.interfaces.reranker import IReranker
from app.core.interfaces.sparse_index import ISparseIndex
from app.core.interfaces.vector_store import IVectorStore


class RetrievalService:

    def __init__(
        self,
        embedding_provider: IEmbeddingProvider,
        vector_store: IVectorStore,
        sparse_index: ISparseIndex,
        reranker: IReranker,
    ):
        self._embeddings = embedding_provider
        self._vector_store = vector_store
        self._sparse_index = sparse_index
        self._reranker = reranker

    def hybrid_search(self, query: str, user_id: str, top_k: int, file_ids: Optional[List[str]] = None) -> List[DocumentChunk]:
        query_vector = self._embeddings.embed_query(query)
        dense_results = self._vector_store.search(query_vector, user_id, top_k=top_k, file_ids=file_ids)
        sparse_results = self._sparse_index.search(user_id, query, top_k=top_k, file_ids=file_ids)

        seen_contents = set()
        combined: List[DocumentChunk] = []
        for doc in dense_results + sparse_results:
            if doc.content not in seen_contents:
                seen_contents.add(doc.content)
                combined.append(doc)
        return combined

    def retrieve_and_rerank(self, query: str, user_id: str, top_k: int, top_n: int, file_ids: Optional[List[str]] = None) -> List[DocumentChunk]:
        candidates = self.hybrid_search(query, user_id, top_k, file_ids=file_ids)
        if not candidates:
            return []
        return self._reranker.rerank(query, candidates, top_n)

    @property
    def reranker(self) -> IReranker:
        """Exposed for callers (e.g. ChatWorkflowService) that need to
        rerank a per-source-grouped candidate set themselves rather than
        via the flat retrieve_and_rerank() convenience method above."""
        return self._reranker
