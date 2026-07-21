import traceback

from fastapi import APIRouter, Depends, Form, HTTPException

from app.api.dependencies import get_container, get_current_user
from app.container import Container
from app.infrastructure.db.models import UserModel

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def secure_chat(
    query: str = Form(...),
    session_id: str = Form(...),
    file_ids: str = Form(None),  # optional comma-separated UploadedFile ids; empty = search all of this user's files
    container: Container = Depends(get_container),
    current_user: UserModel = Depends(get_current_user),
):
    user_id = str(current_user.id)
    try:
        print("\n==============================")
        print("CHAT REQUEST RECEIVED")
        print("==============================")
        print("User:", user_id)
        print("Session:", session_id)
        print("Question:", query)

        selected_file_ids = [f.strip() for f in file_ids.split(",") if f.strip()] if file_ids else []
        if selected_file_ids:
            print("Restricted to file_ids:", selected_file_ids)

        answer = container.chat_workflow_service.run(
            query=query,
            user_id=user_id,
            session_id=session_id,
            selected_file_ids=selected_file_ids,
        )

        print("Generated Response:")
        print(answer.response_text[:300])

        # Persisted to Postgres — survives a restart or a login from a
        # different browser/device.
        container.history_service.save_chat_turn(current_user.id, session_id, query, answer.response_text)

        print("CHAT SUCCESS\n")
        return answer.to_dict()

    except Exception as e:
        print("\nCHAT FAILED")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"LLM Orchestration Error: {str(e)}")
