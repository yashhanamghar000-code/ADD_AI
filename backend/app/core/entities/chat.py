"""Domain entities for the chat/RAG use case."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Citation:
    source: str
    page: Any

    def to_dict(self) -> Dict[str, Any]:
        return {"source": self.source, "page": self.page}


@dataclass
class ChatAnswer:
    """Result of running the RAG workflow for one user turn."""

    response_text: str
    sub_queries_used: List[str] = field(default_factory=list)
    follow_up_questions: List[str] = field(default_factory=list)
    citations: List[Citation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": "success",
            "response": self.response_text,
            "sub_queries_used": self.sub_queries_used,
            "follow_up_questions": self.follow_up_questions,
            "citations": [c.to_dict() for c in self.citations],
        }
