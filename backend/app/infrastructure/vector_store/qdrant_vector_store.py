import uuid
from typing import List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.http.models import (
    Distance, FieldCondition, Filter, MatchAny, MatchValue,
    PayloadSchemaType, PointStruct, SearchParams, VectorParams,
)

from app.core.entities.document import DocumentChunk
from app.core.interfaces.vector_store import IVectorStore


class QdrantVectorStore(IVectorStore):
    """Dense-vector persistence + tenant-filtered similarity search.
    Nothing outside this class knows Qdrant's client/query API — swap it
    for Pinecone/pgvector/etc by writing one new IVectorStore adapter."""

    def __init__(self, url: str, api_key: Optional[str], collection_name: str, embedding_dim: int, batch_size: int = 100):
        self._collection_name = collection_name
        self._batch_size = batch_size
        self._client = QdrantClient(url=url, api_key=api_key, timeout=60.0)
        self._ensure_collection(embedding_dim)

    def _ensure_collection(self, embedding_dim: int) -> None:
        existing = [c.name for c in self._client.get_collections().collections]
        if self._collection_name not in existing:
            self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE),
            )
        self._ensure_payload_indexes()

    def _ensure_payload_indexes(self) -> None:
        """Newer Qdrant server versions require an explicit payload index on
        any field used in a filter — otherwise filtered search fails with
        'Index required but not found'. Idempotent: re-creating an existing
        index is a no-op, and duplicate-index errors are swallowed."""
        for field_name in ("user_id", "session_id", "file_id"):
            try:
                self._client.create_payload_index(
                    collection_name=self._collection_name,
                    field_name=field_name,
                    field_schema=PayloadSchemaType.KEYWORD,
                )
            except UnexpectedResponse:
                pass  # index already exists
            except Exception as e:
                print(f"[Qdrant] Warning: could not ensure index on '{field_name}': {e}")

    def upsert(self, chunks: List[DocumentChunk], vectors: List[List[float]], user_id: str, session_id: str) -> None:
        points = []
        for chunk, vector in zip(chunks, vectors):
            payload = {"text": chunk.content, "user_id": user_id, "session_id": session_id, **chunk.metadata}
            points.append(PointStruct(id=str(uuid.uuid4()), vector=vector, payload=payload))

        # Sent in batches, not one request for the whole file — a
        # multi-hundred-chunk upsert as a single call can time out.
        for i in range(0, len(points), self._batch_size):
            self._client.upsert(collection_name=self._collection_name, points=points[i:i + self._batch_size])

    def search(self, query_vector: List[float], user_id: str, top_k: int, file_ids: Optional[List[str]] = None) -> List[DocumentChunk]:
        must = [FieldCondition(key="user_id", match=MatchValue(value=user_id))]
        if file_ids:
            must.append(FieldCondition(key="file_id", match=MatchAny(any=[str(f) for f in file_ids])))
        qfilter = Filter(must=must)

        # Qdrant's default vector search is APPROXIMATE (HNSW). Once a
        # file_id filter narrows the candidate pool, HNSW's graph walk can
        # finish before reaching a node that satisfies the filter,
        # returning few/zero points even though matching data exists.
        # exact=True forces a real filtered scan whenever a filter is
        # applied, keeping filtered results as reliable as unfiltered ones,
        # while unfiltered (all-files) search keeps its normal ANN speed.
        search_params = SearchParams(exact=True) if file_ids else None

        response = self._client.query_points(
            collection_name=self._collection_name,
            query=query_vector,
            query_filter=qfilter,
            limit=top_k,
            search_params=search_params,
        )
        return [
            DocumentChunk(content=hit.payload.get("text", ""), metadata=hit.payload)
            for hit in response.points
        ]

    def delete_session(self, user_id: str, session_id: str) -> None:
        """Wipes only this user+session's vectors, not the whole collection."""
        qfilter = Filter(must=[
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
            FieldCondition(key="session_id", match=MatchValue(value=session_id)),
        ])
        # wait=True so this call doesn't return until Qdrant has actually
        # applied the delete — otherwise a caller that immediately
        # re-searches (or deletes the Postgres row right after) can race
        # ahead of the deletion.
        self._client.delete(collection_name=self._collection_name, points_selector=qfilter, wait=True)

    def delete_file(self, user_id: str, file_id: str) -> None:
        """Wipes only the vectors belonging to ONE uploaded file, leaving
        that user's other files in this session/chat intact."""
        qfilter = Filter(must=[
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
            FieldCondition(key="file_id", match=MatchValue(value=file_id)),
        ])
        self._client.delete(collection_name=self._collection_name, points_selector=qfilter, wait=True)
