"""
FULL FILE — replace your existing backend/app/api/routers/document_router.py.

Adds the new GET /api/documents/{file_id}/file endpoint that the citation
viewer calls to fetch the original PDF bytes. Same auth + ownership check
as every other route (a user can only ever stream their own files).
"""
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.dependencies import get_container, get_current_user
from app.container import Container
from app.core.exceptions import NotFoundError
from app.infrastructure.db.models import UserModel

router = APIRouter(prefix="/api", tags=["documents"])


@router.delete("/documents/{file_id}")
async def delete_document(
    file_id: str,
    container: Container = Depends(get_container),
    current_user: UserModel = Depends(get_current_user),
):
    user_id = str(current_user.id)

    try:
        int(file_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid file id.")

    try:
        deleted = container.session_service.remove_file(user_id, file_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="File not found.")
    except Exception as e:
        print(f"[Delete] Failed to purge data for file_id={file_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not fully remove this file's data. Please try again.")

    return {
        "status": "success",
        "detail": f"'{deleted['file_name']}' removed.",
        "file_id": file_id,
        "session_id": deleted["session_id"],
    }


@router.get("/documents/{file_id}/file")
async def get_document_file(
    file_id: str,
    container: Container = Depends(get_container),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Streams back the original uploaded PDF for the citation viewer.
    Ownership-checked: a user can only ever fetch a file that belongs to
    one of their own conversations — same pattern as delete_document above.
    """
    try:
        file_id_int = int(file_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid file id.")

    file_record = container.history_service.get_owned_file(current_user.id, file_id_int)
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found.")

    if not file_record.file_path or not os.path.exists(file_record.file_path):
        raise HTTPException(status_code=404, detail="Original file is no longer available on the server.")

    return FileResponse(
        path=file_record.file_path,
        media_type="application/pdf",
        filename=file_record.file_name,
        headers={"Content-Disposition": f'inline; filename="{file_record.file_name}"'},
    )
