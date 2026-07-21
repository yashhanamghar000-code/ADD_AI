"""Read/write orchestration for conversation, chat-message, and file
history — depends only on repository interfaces, so it works identically
whether called from a FastAPI request (main.py) or a Celery worker task
(no shared request lifecycle between the two)."""
from typing import Any, Dict, List

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

    def create_pending_file(self, user_id: int, session_id: str, file_name: str) -> Any:
        """Creates the UploadedFile row up front (status='processing'),
        before async ingestion runs, so we have a stable id to stamp onto
        every chunk this file produces."""
        return self._files.create_pending(user_id, session_id, file_name)

    def list_files_for_conversation(self, user_id: int, session_id: str) -> List[Dict[str, Any]]:
        return self._files.list_for_conversation(user_id, session_id)

    def get_chat_history(self, user_id: int, session_id: str) -> List[Dict[str, Any]]:
        return self._messages.get_history(user_id, session_id)

    def save_chat_turn(self, user_id: int, session_id: str, query: str, response: str) -> None:
        self._messages.save_turn(user_id, session_id, query, response)

    def delete_conversation(self, user_id: int, session_id: str) -> None:
        self._conversations.delete(user_id, session_id)

    def update_file_status(self, file_id: int, status: str, total_chunks_indexed: int = 0) -> None:
        """Called by the ingestion pipeline (Celery worker) once
        parsing/embedding finishes for one uploaded file."""
        self._files.update_status(file_id, status, total_chunks_indexed)
