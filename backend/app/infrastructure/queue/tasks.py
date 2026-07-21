"""
Celery task: the async half of the upload pipeline. Runs in a separate
worker process from FastAPI, so it builds its own Container (with its own
short-lived DB session) via app.container.build_worker_container rather
than reusing anything request-scoped.
"""
import os
import traceback

from app.container import build_worker_container
from app.core.exceptions import IngestionError
from app.infrastructure.queue.celery_app import celery_app


@celery_app.task(bind=True, name="app.tasks.process_document_task")
def process_document_task(self, file_path: str, file_name: str, user_id: str, session_id: str, file_id: str):
    container, db = build_worker_container()
    try:
        self.update_state(state="PARSING", meta={"stage": "parsing_document"})

        if not os.path.exists(file_path):
            container.history_service.update_file_status(int(file_id), "failed")
            return {"status": "failed", "detail": f"File not found on worker storage lane: {file_path}"}

        print(f"[Tasks] Handing off file path directly to parsing engine: {file_path} (file_id={file_id})")

        self.update_state(state="EMBEDDING", meta={"stage": "embedding_and_indexing"})
        try:
            total_chunks_indexed = container.ingestion_service.ingest(
                file_path=file_path,
                file_name=file_name,
                user_id=user_id,
                session_id=session_id,
                file_id=file_id,
            )
        except IngestionError as e:
            container.history_service.update_file_status(int(file_id), "failed")
            return {"status": "failed", "detail": str(e)}
        finally:
            _cleanup_temp_file(file_path)

        container.history_service.update_file_status(int(file_id), "indexed", total_chunks_indexed)

        return {
            "status": "success",
            "total_chunks_indexed": total_chunks_indexed,
            "file_name": file_name,
            "file_id": file_id,
        }

    except Exception as e:
        traceback.print_exc()
        _cleanup_temp_file(file_path)
        try:
            container.history_service.update_file_status(int(file_id), "failed")
        except Exception:
            pass
        return {"status": "failed", "detail": str(e)}
    finally:
        db.close()


def _cleanup_temp_file(file_path: str) -> None:
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"[Tasks] Cleaned up temporary file: {file_path}")
    except Exception as cleanup_error:
        print(f"Warning: Failed to delete temporary file {file_path}: {cleanup_error}")
