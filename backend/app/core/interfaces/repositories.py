"""
Repository interfaces (Repository pattern) — the service layer talks to
these, never to SQLAlchemy directly. That's what lets `services/` be
unit-tested with an in-memory fake and lets the persistence technology
(Postgres today) change without touching business logic.

Each interface is intentionally narrow (Interface Segregation) — a service
that only ever reads users doesn't need to depend on file/message methods.
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
    def create_pending(self, user_id: int, session_id: str, file_name: str) -> Any:
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
