from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.core.interfaces.repositories import IChatMessageRepository, IConversationRepository
from app.infrastructure.db.models import ChatMessageModel, ConversationModel


class SqlAlchemyChatMessageRepository(IChatMessageRepository):

    def __init__(self, db: Session, conversation_repository: IConversationRepository):
        self._db = db
        self._conversations = conversation_repository

    def save_turn(self, user_id: int, session_id: str, query: str, response: str) -> None:
        conv = self._conversations.get_or_create(user_id, session_id, title_hint=query)
        self._db.add(ChatMessageModel(conversation_id=conv.id, user_id=user_id, role="user", message=query))
        self._db.add(ChatMessageModel(conversation_id=conv.id, user_id=user_id, role="assistant", message=response))
        self._db.commit()

    def get_history(self, user_id: int, session_id: str) -> List[Dict[str, Any]]:
        conv = self._db.query(ConversationModel).filter(
            ConversationModel.session_id == session_id,
            ConversationModel.user_id == user_id,
        ).first()
        if not conv:
            return []
        return [
            {"sender": "user" if m.role == "user" else "bot", "text": m.message}
            for m in sorted(conv.messages, key=lambda m: m.created_at)
        ]
