"""
FULL FILE — replace your existing backend/app/core/entities/chat.py.
Citation carries file_id (to fetch the right PDF), snippet (matched text
for the frontend to highlight on normal pages), and bbox/page_width/
page_height (exact highlight region for OCR'd/scanned pages, which have
no embedded PDF text layer to search).
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
    # Present only for OCR'd (scanned) pages, where there's no embedded PDF
    # text layer for the frontend to search — bbox is the exact region (in
    # PDF point space) to highlight instead, computed server-side from the
    # OCR word bounding boxes. page_width/page_height are needed by the
    # frontend to scale bbox into its rendered canvas coordinates.
    bbox: Optional[Dict[str, float]] = None
    page_width: Optional[float] = None
    page_height: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "page": self.page,
            "file_id": self.file_id,
            "snippet": self.snippet,
            "bbox": self.bbox,
            "page_width": self.page_width,
            "page_height": self.page_height,
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