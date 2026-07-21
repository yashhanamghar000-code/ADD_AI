"""
FULL FILE — replace your existing backend/app/api/routers/upload_router.py.

Change vs. your current version: the incoming file is now written straight
to `settings.storage_dir/<user_id>/<file_id-placeholder>_<filename>`
instead of a throwaway temp_uploads path — this permanent copy is what the
citation viewer streams back later. The Celery task receives that same
permanent path and now leaves the file in place after ingestion (see the
updated tasks.py) instead of deleting it.
"""
import os
import traceback
import uuid

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.dependencies import get_container, get_current_user
from app.config.settings import settings
from app.container import Container
from app.infrastructure.db.models import UserModel
from app.infrastructure.queue.celery_app import celery_app
from app.infrastructure.queue.tasks import process_document_task

router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload")
async def upload_document(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    container: Container = Depends(get_container),
    current_user: UserModel = Depends(get_current_user),
):
    user_id = str(current_user.id)
    try:
        print("\n==============================")
        print("UPLOAD REQUEST RECEIVED")
        print("==============================")
        print("User:", user_id)
        print("Session:", session_id)
        print("File:", file.filename)

        # Permanent, per-user storage directory — NOT a temp dir. The file
        # written here is what the citation viewer re-opens later, so it
        # must survive past ingestion.
        user_storage_dir = os.path.join(settings.storage_dir, user_id)
        os.makedirs(user_storage_dir, exist_ok=True)

        unique_prefix = uuid.uuid4().hex
        safe_filename = f"{unique_prefix}_{file.filename}"
        permanent_file_path = os.path.join(user_storage_dir, safe_filename)

        file_has_content = False
        with open(permanent_file_path, "wb") as buffer:
            while chunk := await file.read(65536):
                file_has_content = True
                buffer.write(chunk)

        if not file_has_content:
            if os.path.exists(permanent_file_path):
                os.remove(permanent_file_path)
            raise HTTPException(status_code=422, detail="Uploaded file is empty.")

        file_record = container.history_service.create_pending_file(
            current_user.id, session_id, file.filename, permanent_file_path
        )
        file_id = str(file_record.id)

        task = process_document_task.delay(permanent_file_path, file.filename, user_id, session_id, file_id)

        print(f"Enqueued Celery task: {task.id} (file_id={file_id})\n")

        return {"status": "queued", "task_id": task.id, "file_id": file_id}

    except HTTPException:
        raise
    except Exception as e:
        print("\nUPLOAD FAILED")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/upload/status/{task_id}")
async def upload_status(task_id: str, current_user: UserModel = Depends(get_current_user)):
    result = AsyncResult(task_id, app=celery_app)

    if result.state == "PENDING":
        return {"state": "PENDING", "detail": "Task not found or not yet started."}
    if result.state in ("PARSING", "EMBEDDING"):
        return {"state": result.state, "detail": (result.info or {}).get("stage")}
    if result.state == "SUCCESS":
        return {"state": "SUCCESS", **(result.result or {})}
    if result.state == "FAILURE":
        return {"state": "FAILURE", "detail": str(result.info)}
    return {"state": result.state}
