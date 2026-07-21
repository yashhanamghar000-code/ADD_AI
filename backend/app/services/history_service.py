"""
FULL FILE — replace your existing backend/app/services/history_service.py.
Only change: create_pending_file() now takes/forwards file_path, and a new
get_owned_file() helper exposes ownership-checked lookup for the streaming
endpoint (so the router doesn't need to reach into the file repository
directly).
"""
from typing import Any, Dict, List, Optional

from app.core.interfaces.repositories import (
    IChatMessageRepository, IConversationRepository, IFileRepository,
)


class HistoryService:

    def __init__(
        self,
        conversation_repository: IConversationRepository,
        chat_message_repository: IChatMessageRepository,
        file_repository: IFileRepository,
    ):
        self._conversations = conversation_repository
        self._messages = chat_message_repository
        self._files = file_repository

    def list_conversations(self, user_id: int) -> List[Dict[str, Any]]:
        return self._conversations.list_for_user(user_id)

    def create_pending_file(self, user_id: int, session_id: str, file_name: str, file_path: str) -> Any:
        """Creates the UploadedFile row up front (status='processing'),
        before async ingestion runs, storing where the permanent original
        copy lives on disk (used later by the citation viewer)."""
        return self._files.create_pending(user_id, session_id, file_name, file_path)

    def get_owned_file(self, user_id: int, file_id: int) -> Optional[Any]:
        """Ownership-checked lookup of one uploaded file's record —
        used by the citation PDF-streaming endpoint."""
        return self._files.get_owned(user_id, file_id)

    def list_files_for_conversation(self, user_id: int, session_id: str) -> List[Dict[str, Any]]:
        return self._files.list_for_conversation(user_id, session_id)

    def get_chat_history(self, user_id: int, session_id: str) -> List[Dict[str, Any]]:
        return self._messages.get_history(user_id, session_id)

    def save_chat_turn(self, user_id: int, session_id: str, query: str, response: str) -> None:
        self._messages.save_turn(user_id, session_id, query, response)

    def delete_conversation(self, user_id: int, session_id: str) -> None:
        self._conversations.delete(user_id, session_id)

    def update_file_status(self, file_id: int, status: str, total_chunks_indexed: int = 0) -> None:
        self._files.update_status(file_id, status, total_chunks_indexed)
