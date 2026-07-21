"""
Use case: turn one uploaded file into searchable chunks.

Orchestrates ParserFactory -> IDocumentChunker -> IEmbeddingProvider ->
IVectorStore -> ISparseIndex. Every collaborator is an interface, so this
class has exactly one reason to change: the *sequence of ingestion steps*
itself (Single Responsibility) — not how PDFs are parsed, not how vectors
are stored, not how BM25 caches are kept.
"""
from typing import List

from app.core.entities.document import DocumentChunk
from app.core.exceptions import IngestionError
from app.core.interfaces.embedding_provider import IEmbeddingProvider
from app.core.interfaces.document_parser import IDocumentChunker
from app.core.interfaces.sparse_index import ISparseIndex
from app.core.interfaces.vector_store import IVectorStore
from app.infrastructure.parsing.parser_factory import ParserFactory, UnsupportedFileTypeError
from app.infrastructure.parsing.chunk_audit_logger import ChunkAuditLogger


class IngestionService:

    def __init__(
        self,
        parser_factory: ParserFactory,
        chunker: IDocumentChunker,
        embedding_provider: IEmbeddingProvider,
        vector_store: IVectorStore,
        sparse_index: ISparseIndex,
        audit_logger: ChunkAuditLogger,
    ):
        self._parser_factory = parser_factory
        self._chunker = chunker
        self._embeddings = embedding_provider
        self._vector_store = vector_store
        self._sparse_index = sparse_index
        self._audit_logger = audit_logger

    def ingest(self, file_path: str, file_name: str, user_id: str, session_id: str, file_id: str) -> int:
        """Parses, chunks, embeds, and indexes one file. Returns the number
        of chunks indexed. Raises IngestionError if nothing could be
        extracted or indexing failed."""
        tenant_metadata = {"user_id": user_id, "session_id": session_id, "file_id": file_id}

        try:
            parser = self._parser_factory.get_parser(file_name)
        except UnsupportedFileTypeError as e:
            raise IngestionError(str(e)) from e

        print(f"\n[Ingestion] User: {user_id} | Session: {session_id} | File: {file_id} | Processing: {file_name}")
        raw_documents = parser.parse(file_path, file_name, tenant_metadata)
        if not raw_documents:
            raise IngestionError("No text could be extracted from the file.")

        chunks: List[DocumentChunk] = self._chunker.chunk(raw_documents)
        self._audit_logger.log(chunks, file_name, user_id, session_id)

        if not chunks:
            raise IngestionError("No text could be extracted from the file.")

        self._index(chunks, user_id, session_id)
        return len(chunks)

    def _index(self, chunks: List[DocumentChunk], user_id: str, session_id: str) -> None:
        texts = [c.content for c in chunks]
        vectors = self._embeddings.embed_documents(texts)

        # session_id is still stamped onto every chunk's payload (so
        # "clear this chat's documents" and citations still know which
        # upload/conversation a chunk came from) even though it's not used
        # as a search filter in retrieval — see RetrievalService.
        self._vector_store.upsert(chunks, vectors, user_id, session_id)
        self._sparse_index.add_documents(user_id, chunks)
