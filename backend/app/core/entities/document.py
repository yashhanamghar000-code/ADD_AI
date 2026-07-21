"""
Domain entity for a single unit of parsed/embeddable document text.

This is the ONE shape every layer of the system agrees on. Parsers produce
it, the chunker splits it, embedding providers embed its `content`, vector
stores persist it, and retrieval/rerank return lists of it. Nothing outside
`core/` and `infrastructure/` needs to know it happens to be backed by a
LangChain `Document` under the hood in a couple of adapters — which is what
lets us swap chunking/vector libraries later without touching services or
API code (Dependency Inversion in practice).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class DocumentChunk:
    """A piece of extracted text plus the metadata needed to trace it back
    to its source file/page and its tenant (user/session/file)."""

    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def source(self) -> str:
        return self.metadata.get("source", "unknown")

    @property
    def page(self) -> Any:
        return self.metadata.get("page")

    @property
    def user_id(self) -> str | None:
        return self.metadata.get("user_id")

    @property
    def session_id(self) -> str | None:
        return self.metadata.get("session_id")

    @property
    def file_id(self) -> str | None:
        return self.metadata.get("file_id")
