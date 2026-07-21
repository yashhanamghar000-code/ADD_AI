from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_container, get_current_user
from app.container import Container
from app.infrastructure.db.models import UserModel

router = APIRouter(prefix="/api", tags=["conversations"])


@router.get("/conversations")
async def list_conversations(
    container: Container = Depends(get_container),
    current_user: UserModel = Depends(get_current_user),
):
    return {"conversations": container.history_service.list_conversations(current_user.id)}


@router.get("/conversations/{session_id}/files")
async def list_conversation_files(
    session_id: str,
    container: Container = Depends(get_container),
    current_user: UserModel = Depends(get_current_user),
):
    return {"files": container.history_service.list_files_for_conversation(current_user.id, session_id)}


@router.get("/chat/history/{user_id}/{session_id}")
async def get_chat_history(
    user_id: str,
    session_id: str,
    container: Container = Depends(get_container),
    current_user: UserModel = Depends(get_current_user),
):
    # A logged-in user can only ever read their own history, regardless of
    # what user_id shows up in the URL.
    if str(current_user.id) != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this history.")
    return {"history": container.history_service.get_chat_history(current_user.id, session_id)}
