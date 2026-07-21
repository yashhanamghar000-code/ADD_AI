"""
Interface Segregation: a parser only needs to know how to turn ONE file
type into DocumentChunks. It does NOT know about chunking, embedding,
storage, or tenancy rules beyond stamping the metadata it's given.
"""
from abc import ABC, abstractmethod
from typing import Dict, List

from app.core.entities.document import DocumentChunk


class IDocumentParser(ABC):
    @abstractmethod
    def supports(self, file_extension: str) -> bool:
        """True if this parser can handle the given (lowercase, dotted) extension."""
        raise NotImplementedError

    @abstractmethod
    def parse(self, file_path: str, file_name: str, tenant_metadata: Dict[str, str]) -> List[DocumentChunk]:
        """Extract raw (pre-chunking) DocumentChunks from a file on disk.

        `tenant_metadata` (user_id/session_id/file_id) must be merged into
        every returned chunk's metadata so ownership survives into storage.
        """
        raise NotImplementedError


class IDocumentChunker(ABC):
    """Splits oversized parsed documents into retrieval-sized chunks.
    Kept separate from IDocumentParser (SRP) — chunking strategy is a
    cross-cutting concern independent of *how* text was extracted."""

    @abstractmethod
    def chunk(self, documents: List[DocumentChunk]) -> List[DocumentChunk]:
        raise NotImplementedError
