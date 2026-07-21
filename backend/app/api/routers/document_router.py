from fastapi import APIRouter, Depends, HTTPException

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
    """Removes ONE uploaded file (e.g. one of two Tata PDFs) without
    clearing the whole chat/session. See SessionService.remove_file for
    the ordering guarantee (vectors purged before the Postgres row)."""
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
