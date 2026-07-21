from abc import ABC, abstractmethod
from typing import List, Optional, Tuple


class ILLMClient(ABC):
    """A single chat-completion call. Every prompt-engineering detail lives
    in the service layer that calls this — the client itself only knows
    how to talk to whichever LLM backend it wraps (Azure OpenAI today)."""

    @abstractmethod
    def complete(self, messages: List[Tuple[str, str]]) -> str:
        """`messages` is a list of (role, content) pairs, role in
        {"system", "user"}. Returns the raw text of the model's reply."""
        raise NotImplementedError
