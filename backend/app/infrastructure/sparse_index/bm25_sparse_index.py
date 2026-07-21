import os
import pickle
from typing import List, Optional

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document as LcDocument

from app.core.entities.document import DocumentChunk
from app.core.interfaces.sparse_index import ISparseIndex


class Bm25SparseIndex(ISparseIndex):
    """Keyword/BM25 sparse retrieval, one pickle cache per user, merged
    across every chat that user has ever uploaded into (not per session) —
    this is what lets a brand new chat retrieve documents uploaded in a
    different, older chat for the same user."""

    def __init__(self, cache_dir: str):
        self._cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _cache_path(self, user_id: str) -> str:
        return os.path.join(self._cache_dir, f"bm25_{user_id}.pkl")

    def add_documents(self, user_id: str, chunks: List[DocumentChunk]) -> None:
        if not chunks:
            return

        lc_chunks = [LcDocument(page_content=c.content, metadata=c.metadata) for c in chunks]

        cache_path = self._cache_path(user_id)
        existing_docs: List[LcDocument] = []
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "rb") as f:
                    existing_retriever = pickle.load(f)
                    existing_docs = list(existing_retriever.docs)
            except Exception as e:
                print(f"[BM25] Could not load existing user-wide cache, rebuilding fresh: {e}")

        combined_docs = existing_docs + lc_chunks
        bm25_retriever = BM25Retriever.from_documents(combined_docs)
        with open(cache_path, "wb") as f:
            pickle.dump(bm25_retriever, f)

        print(f"[DEBUG] Ingested {len(chunks)} chunks for user={user_id} "
              f"(user-wide BM25 index now has {len(combined_docs)} total chunks)")

    def search(self, user_id: str, query: str, top_k: int, file_ids: Optional[List[str]] = None) -> List[DocumentChunk]:
        cache_path = self._cache_path(user_id)
        if not os.path.exists(cache_path):
            return []

        with open(cache_path, "rb") as f:
            bm25_retriever = pickle.load(f)

        raw_results = bm25_retriever.invoke(query)

        # BM25Retriever has no built-in metadata filter, so post-filter to
        # the selected file_ids here. Cast both sides to str so this can't
        # silently miss matches if a file_id ever ends up as an int
        # somewhere upstream.
        if file_ids:
            wanted = {str(f) for f in file_ids}
            raw_results = [d for d in raw_results if str(d.metadata.get("file_id")) in wanted]

        return [DocumentChunk(content=d.page_content, metadata=d.metadata) for d in raw_results[:top_k]]

    def remove_file(self, user_id: str, file_id: str) -> None:
        """Rebuilds the user-wide cache with this file's chunks dropped, so
        a 'deleted' file stops surfacing via sparse search immediately
        rather than lingering until the user's next upload."""
        cache_path = self._cache_path(user_id)
        if not os.path.exists(cache_path):
            return

        with open(cache_path, "rb") as f:
            bm25_retriever = pickle.load(f)

        remaining_docs = [d for d in bm25_retriever.docs if d.metadata.get("file_id") != file_id]

        if remaining_docs:
            new_retriever = BM25Retriever.from_documents(remaining_docs)
            with open(cache_path, "wb") as f:
                pickle.dump(new_retriever, f)
        else:
            os.remove(cache_path)
