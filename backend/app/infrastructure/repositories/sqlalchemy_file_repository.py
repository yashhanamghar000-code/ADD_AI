"""
FULL FILE — replace your existing
backend/app/infrastructure/repositories/sqlalchemy_file_repository.py.
Changes: create_pending() now stores file_path; get_owned()'s result
(already returned as the ORM object) exposes .file_path for the new
streaming endpoint; delete() now also returns file_path so the caller can
remove the file from disk.
"""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.interfaces.repositories import IConversationRepository, IFileRepository
from app.infrastructure.db.models import ConversationModel, UploadedFileModel


class SqlAlchemyFileRepository(IFileRepository):

    def __init__(self, db: Session, conversation_repository: IConversationRepository):
        self._db = db
        self._conversations = conversation_repository

    def create_pending(self, user_id: int, session_id: str, file_name: str, file_path: str) -> UploadedFileModel:
        conv = self._conversations.get_or_create(user_id, session_id, title_hint=file_name)
        f = UploadedFileModel(
            conversation_id=conv.id,
            user_id=user_id,
            file_name=file_name,
            status="processing",
            total_chunks_indexed=0,
            file_path=file_path,
        )
        self._db.add(f)
        self._db.commit()
        self._db.refresh(f)
        return f

    def update_status(self, file_id: int, status: str, total_chunks_indexed: int = 0) -> None:
        f = self._db.query(UploadedFileModel).filter(UploadedFileModel.id == file_id).first()
        if f:
            f.status = status
            f.total_chunks_indexed = total_chunks_indexed
            self._db.commit()

    def get_owned(self, user_id: int, file_id: int) -> Optional[UploadedFileModel]:
        return (
            self._db.query(UploadedFileModel)
            .join(ConversationModel, UploadedFileModel.conversation_id == ConversationModel.id)
            .filter(UploadedFileModel.id == file_id, ConversationModel.user_id == user_id)
            .first()
        )

    def delete(self, user_id: int, file_id: int) -> Optional[Dict[str, Any]]:
        f = self.get_owned(user_id, file_id)
        if not f:
            return None
        info = {"file_name": f.file_name, "session_id": f.conversation.session_id, "file_path": f.file_path}
        self._db.delete(f)
        self._db.commit()
        return info

    def list_for_conversation(self, user_id: int, session_id: str) -> List[Dict[str, Any]]:
        conv = self._db.query(ConversationModel).filter(
            ConversationModel.session_id == session_id,
            ConversationModel.user_id == user_id,
        ).first()
        if not conv:
            return []
        return [
            {
                "id": str(f.id),
                "name": f.file_name,
                "status": f.status,
                "total_chunks_indexed": f.total_chunks_indexed,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in sorted(conv.files, key=lambda f: f.created_at)
        ]
