"""
FULL FILE — replace your existing backend/app/core/interfaces/repositories.py.
Only change: IFileRepository.create_pending() now also accepts/returns a
`file_path` (where the permanent original PDF lives on disk).
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IUserRepository(ABC):
    @abstractmethod
    def get_by_email(self, email: str) -> Optional[Any]:
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, user_id: int) -> Optional[Any]:
        raise NotImplementedError

    @abstractmethod
    def create(self, name: str, email: str, hashed_password: str) -> Any:
        raise NotImplementedError


class IConversationRepository(ABC):
    @abstractmethod
    def get_or_create(self, user_id: int, session_id: str, title_hint: str) -> Any:
        raise NotImplementedError

    @abstractmethod
    def list_for_user(self, user_id: int) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def delete(self, user_id: int, session_id: str) -> None:
        raise NotImplementedError


class IChatMessageRepository(ABC):
    @abstractmethod
    def save_turn(self, user_id: int, session_id: str, query: str, response: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_history(self, user_id: int, session_id: str) -> List[Dict[str, Any]]:
        raise NotImplementedError


class IFileRepository(ABC):
    @abstractmethod
    def create_pending(self, user_id: int, session_id: str, file_name: str, file_path: str) -> Any:
        raise NotImplementedError

    @abstractmethod
    def update_status(self, file_id: int, status: str, total_chunks_indexed: int = 0) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_owned(self, user_id: int, file_id: int) -> Optional[Any]:
        raise NotImplementedError

    @abstractmethod
    def delete(self, user_id: int, file_id: int) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def list_for_conversation(self, user_id: int, session_id: str) -> List[Dict[str, Any]]:
        raise NotImplementedError
