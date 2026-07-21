"""Single-responsibility: writes a human-readable audit trail of every
chunk produced for a file, for debugging what actually got indexed.
Kept separate from IngestionService so ingestion orchestration doesn't
also own file-system logging concerns."""
import os
from typing import List

from app.core.entities.document import DocumentChunk


class ChunkAuditLogger:

    def __init__(self, log_dir: str):
        self._log_dir = log_dir

    def log(self, chunks: List[DocumentChunk], file_name: str, user_id: str, session_id: str) -> None:
        os.makedirs(self._log_dir, exist_ok=True)
        log_path = os.path.join(self._log_dir, f"audit_{user_id}_{session_id}.txt")

        with open(log_path, "a", encoding="utf-8") as txt_file:
            txt_file.write(f"=== CHUNK AUDIT LOG: {file_name} | {len(chunks)} SEGMENTS ===\n\n")
            for idx, chunk in enumerate(chunks, start=1):
                txt_file.write(f"--- CHUNK {idx} | Source: {chunk.source} | Page: {chunk.page} ---\n")
                txt_file.write(chunk.content)
                txt_file.write("\n\n" + "=" * 50 + "\n\n")
