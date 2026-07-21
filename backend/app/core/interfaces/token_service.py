from abc import ABC, abstractmethod
from typing import Optional


class ITokenService(ABC):
    """Issues and verifies auth tokens. Swappable: JWT today; opaque
    session tokens / OAuth introspection tomorrow."""

    @abstractmethod
    def issue_token(self, user_id: int) -> str:
        raise NotImplementedError

    @abstractmethod
    def verify_token(self, token: str) -> Optional[int]:
        """Returns the user_id encoded in the token, or None if invalid/expired."""
        raise NotImplementedError
