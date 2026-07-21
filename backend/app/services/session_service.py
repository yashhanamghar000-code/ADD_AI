"""
FULL FILE — replace your existing backend/app/services/session_service.py.
Only change: remove_file() now also deletes the permanently-stored
original PDF from disk (the citation-viewer copy), since it's no longer
cleaned up automatically after ingestion.
"""
import os
from typing import Any, Dict

from app.core.exceptions import NotFoundError
from app.core.interfaces.repositories import IConversationRepository, IFileRepository
from app.core.interfaces.sparse_index import ISparseIndex
from app.core.interfaces.vector_store import IVectorStore


class SessionService:

    def __init__(
        self,
        vector_store: IVectorStore,
        sparse_index: ISparseIndex,
        conversation_repository: IConversationRepository,
        file_repository: IFileRepository,
    ):
        self._vector_store = vector_store
        self._sparse_index = sparse_index
        self._conversations = conversation_repository
        self._files = file_repository

    def clear_session(self, user_id: str, session_id: str) -> None:
        self._vector_store.delete_session(user_id, session_id)
        self._conversations.delete(int(user_id), session_id)

    def remove_file(self, user_id: str, file_id: str) -> Dict[str, Any]:
        owned = self._files.get_owned(int(user_id), int(file_id))
        if not owned:
            raise NotFoundError("File not found.")

        self._vector_store.delete_file(user_id, file_id)
        self._sparse_index.remove_file(user_id, file_id)

        deleted = self._files.delete(int(user_id), int(file_id))
        if not deleted:
            raise NotFoundError("File not found.")

        # Clean up the permanent original copy on disk (citation-viewer
        # storage) now that nothing references this file anymore.
        stored_path = deleted.get("file_path")
        if stored_path and os.path.exists(stored_path):
            try:
                os.remove(stored_path)
            except Exception as e:
                print(f"[SessionService] Warning: could not delete stored file '{stored_path}': {e}")

        return deleted
