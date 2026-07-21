"""
FULL FILE — replace your existing backend/app/core/entities/chat.py.
Citation now carries `file_id` (to fetch the right PDF) and `snippet`
(the actual matched text, used by the frontend to highlight it on the
page) in addition to source/page.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Citation:
    source: str
    page: Any
    file_id: Optional[str] = None
    snippet: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "page": self.page,
            "file_id": self.file_id,
            "snippet": self.snippet,
        }


@dataclass
class ChatAnswer:
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
