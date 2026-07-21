from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.core.interfaces.repositories import IConversationRepository
from app.infrastructure.db.models import ConversationModel


class SqlAlchemyConversationRepository(IConversationRepository):

    def __init__(self, db: Session):
        self._db = db

    def get_or_create(self, user_id: int, session_id: str, title_hint: str) -> ConversationModel:
        conv = self._db.query(ConversationModel).filter(
            ConversationModel.session_id == session_id
        ).first()
        if conv:
            if conv.user_id != user_id:
                raise PermissionError("session_id belongs to a different user")
            return conv

        conv = ConversationModel(session_id=session_id, user_id=user_id, title=title_hint[:60])
        self._db.add(conv)
        self._db.commit()
        self._db.refresh(conv)
        return conv

    def list_for_user(self, user_id: int) -> List[Dict[str, Any]]:
        convs = (
            self._db.query(ConversationModel)
            .filter(ConversationModel.user_id == user_id)
            .order_by(ConversationModel.updated_at.desc())
            .all()
        )
        return [
            {
                "session_id": c.session_id,
                "title": c.title,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in convs
        ]

    def delete(self, user_id: int, session_id: str) -> None:
        conv = self._db.query(ConversationModel).filter(
            ConversationModel.session_id == session_id,
            ConversationModel.user_id == user_id,
        ).first()
        if conv:
            self._db.delete(conv)  # cascades to messages + files
            self._db.commit()
