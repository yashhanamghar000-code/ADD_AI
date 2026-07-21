# AUDITO AI — SOLID / Low-Level-Design Edition

Multi-tenant financial/legal document RAG platform: FastAPI + LangGraph +
Qdrant (dense) + BM25 (sparse) + Cross-Encoder reranking + JWT auth +
Postgres (users/chats/files) + Celery (async ingestion).

This is a restructuring of the original `AUDITO-base` backend. **No business
logic was changed** — PDF rotation-detection, OCR fallback, hybrid search,
round-robin source grouping, the LangGraph decompose→retrieve→generate
pipeline, and every prompt are byte-for-byte the same behavior as before.
What changed is *how the code is organized*, so it's easier to read, test,
extend, and reuse pieces of in another project.

## Why it's structured this way

| Goal | How this codebase gets there |
|---|---|
| **Maintainability / debugging** | Each class has one job (SRP). A bug in PDF rotation logic can only be in `pdf_parser.py`. A bug in "who can delete a file" can only be in `session_service.py`. You never have to read a 300-line `main.py` to find one bug. |
| **Scalability** | Services don't know about FastAPI, Celery, or each other's internals — only about small interfaces. Adding a new file type, a new vector DB, or a new LLM provider is a new class + one line in `container.py`, not a rewrite. |
| **Reusability / plug-and-play** | Every external dependency (Qdrant, BM25, Azure OpenAI, HuggingFace, bcrypt, JWT) sits behind an interface in `core/interfaces/`. Swap the adapter, keep every service, router, and test unchanged. |

## Architecture (4 layers, dependencies point inward)

```
backend/app/
├── core/                          # Layer 1 — Domain. Zero framework/library imports.
│   ├── entities/                   #   DocumentChunk, Citation, ChatAnswer — plain dataclasses
│   ├── interfaces/                 #   The "ports": IDocumentParser, IEmbeddingProvider,
│   │                                #   IVectorStore, ISparseIndex, IReranker, ILLMClient,
│   │                                #   IPasswordHasher, ITokenService, repository interfaces
│   └── exceptions.py               #   DomainError, AuthenticationError, NotFoundError, ...
│
├── config/settings.py             # Layer 1.5 — single source of config (no os.getenv anywhere else)
│
├── infrastructure/                 # Layer 2 — Adapters. Implements core/interfaces/.
│   ├── parsing/                     #   PdfDocumentParser, DocxDocumentParser, TextDocumentParser,
│   │                                #   ImageOcrDocumentParser, RecursiveDocumentChunker,
│   │                                #   ParserFactory (Strategy + Factory, Open/Closed)
│   ├── embeddings/                  #   HuggingFaceEmbeddingProvider
│   ├── reranking/                   #   CrossEncoderReranker
│   ├── llm/                         #   AzureLlmClient
│   ├── vector_store/                #   QdrantVectorStore
│   ├── sparse_index/                #   Bm25SparseIndex
│   ├── security/                    #   BcryptPasswordHasher, JwtTokenService
│   ├── db/, repositories/           #   SQLAlchemy models + Repository-pattern implementations
│   └── queue/                       #   celery_app.py, tasks.py (the async ingestion worker)
│
├── services/                       # Layer 3 — Use cases. Depend ONLY on core/interfaces/.
│   ├── auth_service.py              #   register / login / verify token
│   ├── ingestion_service.py         #   parse -> chunk -> embed -> index one file
│   ├── retrieval_service.py         #   hybrid search + rerank
│   ├── chat_workflow_service.py     #   the LangGraph RAG pipeline
│   ├── session_service.py           #   clear session / remove one file
│   └── history_service.py           #   conversations, messages, file records
│
├── api/                            # Layer 4 — HTTP. Thin FastAPI routers + Pydantic schemas.
│   ├── routers/                     #   auth, upload, chat, session, document, conversation, health
│   ├── schemas/                     #   request/response models
│   └── dependencies.py              #   get_current_user, get_container
│
├── container.py                    # Composition root — the ONLY file that wires concrete
│                                    #   classes into interfaces. Swap an adapter here, nowhere else.
└── main.py                         # FastAPI app assembly (routers + CORS), ~30 lines
```

**Dependency rule:** `api` → `services` → `core/interfaces` ← `infrastructure`.
Arrows point toward `core`. `core` imports nothing from the other three layers
(**Dependency Inversion Principle**) — that's what makes services testable
with fakes and adapters swappable without touching business logic.

## SOLID, concretely

- **S — Single Responsibility**: `PdfDocumentParser` only parses PDFs.
  `ChunkAuditLogger` only writes debug logs. `SessionService` only handles
  destructive tenant-scoped operations. Nothing does two jobs.
- **O — Open/Closed**: add a new file type by writing one new
  `IDocumentParser` and registering it in `container.py`'s `ParserFactory`
  list — `IngestionService` and every router are untouched.
- **L — Liskov Substitution**: any `IVectorStore` implementation can replace
  `QdrantVectorStore` in `container.py` and `RetrievalService` keeps working,
  because every implementation honors the same contract (same inputs,
  same guarantees).
- **I — Interface Segregation**: `IDocumentParser` doesn't know about
  chunking; `IChatMessageRepository` doesn't know about files. Each
  interface is as narrow as its one caller needs.
- **D — Dependency Inversion**: `services/` never imports Qdrant, SQLAlchemy,
  bcrypt, or LangChain directly — only `core/interfaces/`. `container.py` is
  the one place that knows the concrete implementations exist.

## Running it

```bash
cd AUDITO-AI
cp backend/.env.example backend/.env   # fill in MY_API_KEY, AZURE_OPENAI_ENDPOINT, JWT_SECRET_KEY, etc.
docker compose up --build
```

Backend: `http://localhost:8000` · Postgres: `5432` · Qdrant: `6333` · Redis: `6379`

## API contract (unchanged from the original — your frontend needs zero changes)

- `POST /api/auth/register`, `/login`, `GET /me`, `POST /logout`
- `POST /api/upload` (multipart: `file`, `session_id`) → `{status, task_id, file_id}`
- `GET /api/upload/status/{task_id}`
- `POST /api/chat` (form: `query`, `session_id`, optional `file_ids`)
- `GET /api/conversations`, `GET /api/conversations/{session_id}/files`
- `GET /api/chat/history/{user_id}/{session_id}`
- `DELETE /api/session/{session_id}`, `DELETE /api/documents/{file_id}`

## Extending it (this is the "plug-and-play" part)

| Want to... | Do this |
|---|---|
| Support `.pptx` uploads | Write `PptxDocumentParser(IDocumentParser)` in `infrastructure/parsing/`, add it to the list in `container.py` |
| Swap Qdrant for pgvector | Write `PgVectorStore(IVectorStore)` in `infrastructure/vector_store/`, change one line in `container.py` |
| Swap Azure OpenAI for OpenAI directly | Write `OpenAiLlmClient(ILLMClient)`, change one line in `container.py` |
| Add Elasticsearch alongside BM25 | Write `ElasticsearchSparseIndex(ISparseIndex)` (or a composite that queries both), swap it in `container.py` |
| Unit-test `AuthService` | Construct it with in-memory fakes of `IUserRepository`/`IPasswordHasher`/`ITokenService` — no DB, no FastAPI, no network needed |

## What was intentionally left out of this rebuild

- `legacy_prototypes/code-mm.py` (the original single-user CLI/Chroma
  prototype) — it was reference-only in the source repo and isn't imported
  by the app, so it's not part of the clean architecture.
- `chroma_db/` — Qdrant is the live vector store; Chroma was unused by the
  production path in the source repo.

## Known limitation (carried over, documented rather than silently present)

Clearing a single chat session (`DELETE /api/session/{id}`) removes that
session's vectors from Qdrant immediately, but the user-wide BM25 cache is
additively merged on ingest rather than rebuilt on every delete — cleared
chunks can still surface via sparse search until that user's next upload
rebuilds the cache. See the docstring on `SessionService.clear_session` for
the full trade-off; fixing it fully means rebuilding BM25 from Qdrant's
remaining points on every delete, which is a heavier operation than the
original design took on.
