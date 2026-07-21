"""Use case: destructive tenant-scoped operations — clearing a whole chat
session's documents, or removing one uploaded file."""
from typing import Any, Dict, Optional

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
        """Wipes only the vectors uploaded in THIS chat, leaving that
        user's other chats' documents untouched.

        KNOWN LIMITATION (carried over intentionally): the user-wide BM25
        cache is additively merged on ingest, not rebuilt from the vector
        store on delete — so chunks from a cleared session may still
        surface via sparse search until that user's next upload rebuilds
        the cache from scratch, even though they're gone from the dense
        side. Rebuilding BM25 from the vector store's remaining points on
        every delete would fix this fully but is a heavier operation.
        """
        self._vector_store.delete_session(user_id, session_id)
        self._conversations.delete(int(user_id), session_id)

    def remove_file(self, user_id: str, file_id: str) -> Dict[str, Any]:
        """Deletes one uploaded file's chunks from both indexes, THEN
        deletes its Postgres row — in that order deliberately. If vector
        cleanup fails (timeout, a concurrent upload holding the BM25 cache
        file, a worker restart), the Postgres row stays intact rather than
        vanishing from the UI while its chunks are orphaned and keep
        surfacing in future answers.
        """
        owned = self._files.get_owned(int(user_id), int(file_id))
        if not owned:
            raise NotFoundError("File not found.")

        self._vector_store.delete_file(user_id, file_id)
        self._sparse_index.remove_file(user_id, file_id)

        deleted = self._files.delete(int(user_id), int(file_id))
        if not deleted:
            raise NotFoundError("File not found.")
        return deleted
