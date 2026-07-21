"""
Composition root — the ONE place in the whole application that is allowed
to know about concrete classes. Every other module (services/, api/)
depends only on interfaces from core/interfaces/.

This is what makes the system pluggable: to swap Qdrant for another
vector DB, or Azure for another LLM provider, you write one new
infrastructure/ adapter class and change ONE line below — nothing in
services/ or api/ ever needs to be touched or even re-read.

Two entry points build a Container:
- `build_web_container()`   — used by FastAPI request-scoped dependencies
- `build_worker_container()` — used by the Celery worker (no HTTP request
  lifecycle, so it opens its own short-lived DB session per task)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.config.settings import Settings, settings as default_settings

# Infrastructure adapters
from app.infrastructure.db.database import SessionLocal
from app.infrastructure.repositories.sqlalchemy_user_repository import SqlAlchemyUserRepository
from app.infrastructure.repositories.sqlalchemy_conversation_repository import SqlAlchemyConversationRepository
from app.infrastructure.repositories.sqlalchemy_chat_message_repository import SqlAlchemyChatMessageRepository
from app.infrastructure.repositories.sqlalchemy_file_repository import SqlAlchemyFileRepository
from app.infrastructure.security.bcrypt_password_hasher import BcryptPasswordHasher
from app.infrastructure.security.jwt_token_service import JwtTokenService
from app.infrastructure.parsing.pdf_parser import PdfDocumentParser
from app.infrastructure.parsing.docx_parser import DocxDocumentParser
from app.infrastructure.parsing.text_parser import TextDocumentParser
from app.infrastructure.parsing.image_parser import ImageOcrDocumentParser
from app.infrastructure.parsing.recursive_document_chunker import RecursiveDocumentChunker
from app.infrastructure.parsing.parser_factory import ParserFactory
from app.infrastructure.parsing.chunk_audit_logger import ChunkAuditLogger
from app.infrastructure.embeddings.huggingface_embedding_provider import HuggingFaceEmbeddingProvider
from app.infrastructure.reranking.cross_encoder_reranker import CrossEncoderReranker
from app.infrastructure.llm.azure_llm_client import AzureLlmClient
from app.infrastructure.vector_store.qdrant_vector_store import QdrantVectorStore
from app.infrastructure.sparse_index.bm25_sparse_index import Bm25SparseIndex

# Services (use cases)
from app.services.auth_service import AuthService
from app.services.history_service import HistoryService
from app.services.ingestion_service import IngestionService
from app.services.retrieval_service import RetrievalService
from app.services.session_service import SessionService
from app.services.chat_workflow_service import ChatWorkflowService


class SharedSingletons:
    """
    Heavyweight, stateless-ish infrastructure that is expensive to build
    (loads ML models, opens network clients) and safe to share across
    every request/task in this process. Built exactly once per process.
    """

    def __init__(self, cfg: Settings):
        cfg.ensure_directories()

        self.embedding_provider = HuggingFaceEmbeddingProvider(cfg.embedding_model)
        self.reranker = CrossEncoderReranker(cfg.reranker_model)
        self.llm_client = AzureLlmClient(
            deployment=cfg.azure_llm_deployment,
            api_version=cfg.azure_openai_api_version,
            api_key=cfg.azure_api_key,
            endpoint=cfg.azure_endpoint,
            temperature=cfg.llm_temperature,
        )
        self.vector_store = QdrantVectorStore(
            url=cfg.qdrant_url,
            api_key=cfg.qdrant_api_key,
            collection_name=cfg.qdrant_collection_name,
            embedding_dim=cfg.embedding_dim,
        )
        self.sparse_index = Bm25SparseIndex(cfg.bm25_cache_dir)

        self.parser_factory = ParserFactory([
            PdfDocumentParser(max_workers=cfg.parser_max_workers),
            DocxDocumentParser(),
            TextDocumentParser(),
            ImageOcrDocumentParser(),
        ])
        self.chunker = RecursiveDocumentChunker()
        self.audit_logger = ChunkAuditLogger(cfg.debug_logs_dir)

        self.retrieval_service = RetrievalService(
            embedding_provider=self.embedding_provider,
            vector_store=self.vector_store,
            sparse_index=self.sparse_index,
            reranker=self.reranker,
        )
        self.ingestion_service = IngestionService(
            parser_factory=self.parser_factory,
            chunker=self.chunker,
            embedding_provider=self.embedding_provider,
            vector_store=self.vector_store,
            sparse_index=self.sparse_index,
            audit_logger=self.audit_logger,
        )
        self.chat_workflow_service = ChatWorkflowService(
            llm_client=self.llm_client,
            retrieval_service=self.retrieval_service,
            top_k_per_query=cfg.top_k_per_query,
            final_docs_per_query=cfg.final_docs_per_query,
            max_total_context_docs=cfg.max_total_context_docs,
        )


@dataclass
class Container:
    """Per-request (or per-task) bundle of services, built cheaply on top
    of the process-wide SharedSingletons and a request-scoped DB session."""

    auth_service: AuthService
    history_service: HistoryService
    session_service: SessionService
    ingestion_service: IngestionService
    chat_workflow_service: ChatWorkflowService


_singletons: Optional[SharedSingletons] = None


def _get_singletons(cfg: Settings) -> SharedSingletons:
    global _singletons
    if _singletons is None:
        print("[Container] Booting shared singletons (models, vector store, reranker, LLM client)...")
        _singletons = SharedSingletons(cfg)
        print("[Container] Shared singletons ready.")
    return _singletons


def build_container(db: Session, cfg: Settings = default_settings) -> Container:
    """Builds a Container scoped to one DB session — safe to call once per
    FastAPI request or once per Celery task."""
    shared = _get_singletons(cfg)

    user_repo = SqlAlchemyUserRepository(db)
    conversation_repo = SqlAlchemyConversationRepository(db)
    chat_message_repo = SqlAlchemyChatMessageRepository(db, conversation_repo)
    file_repo = SqlAlchemyFileRepository(db, conversation_repo)

    password_hasher = BcryptPasswordHasher()
    token_service = JwtTokenService(
        secret_key=cfg.jwt_secret_key,
        algorithm=cfg.jwt_algorithm,
        expire_minutes=cfg.jwt_expire_minutes,
    )

    return Container(
        auth_service=AuthService(user_repo, password_hasher, token_service),
        history_service=HistoryService(conversation_repo, chat_message_repo, file_repo),
        session_service=SessionService(shared.vector_store, shared.sparse_index, conversation_repo, file_repo),
        ingestion_service=shared.ingestion_service,
        chat_workflow_service=shared.chat_workflow_service,
    )


def build_worker_container(cfg: Settings = default_settings) -> tuple[Container, Session]:
    """For the Celery worker: no FastAPI request to hang a DB session off
    of, so it opens (and the caller must close) its own short-lived
    session directly against the same Postgres instance."""
    db = SessionLocal()
    return build_container(db, cfg), db
