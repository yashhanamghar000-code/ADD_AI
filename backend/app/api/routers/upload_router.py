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
    """Stages incoming payloads to local temp disk before handing a path
    reference down into Celery — keeps large files off the Redis broker."""
    user_id = str(current_user.id)
    try:
        print("\n==============================")
        print("UPLOAD REQUEST RECEIVED")
        print("==============================")
        print("User:", user_id)
        print("Session:", session_id)
        print("File:", file.filename)

        os.makedirs(settings.temp_upload_dir, exist_ok=True)
        unique_prefix = uuid.uuid4().hex
        safe_filename = f"{unique_prefix}_{file.filename}"
        local_file_path = os.path.join(settings.temp_upload_dir, safe_filename)

        file_has_content = False
        with open(local_file_path, "wb") as buffer:
            while chunk := await file.read(65536):  # 64KB chunks
                file_has_content = True
                buffer.write(chunk)

        if not file_has_content:
            if os.path.exists(local_file_path):
                os.remove(local_file_path)
            raise HTTPException(status_code=422, detail="Uploaded file is empty.")

        # Postgres row created UP FRONT (status="processing") so we have a
        # stable file_id before the worker even starts — that id gets
        # stamped onto every chunk this file produces.
        file_record = container.history_service.create_pending_file(current_user.id, session_id, file.filename)
        file_id = str(file_record.id)

        task = process_document_task.delay(local_file_path, file.filename, user_id, session_id, file_id)

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
    """Poll from the frontend to drive the 'parsing stages' UI."""
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
