"""
FULL FILE — replace your existing backend/app/infrastructure/queue/tasks.py.

Only change vs. your current version: the original uploaded file is no
longer deleted after ingestion. It now lives permanently under
settings.storage_dir and is what the citation viewer streams back when a
user clicks a citation — so it has to stay on disk.
"""
import traceback

from app.container import build_worker_container
from app.core.exceptions import IngestionError
from app.infrastructure.queue.celery_app import celery_app


@celery_app.task(bind=True, name="app.tasks.process_document_task")
def process_document_task(self, file_path: str, file_name: str, user_id: str, session_id: str, file_id: str):
    container, db = build_worker_container()
    try:
        self.update_state(state="PARSING", meta={"stage": "parsing_document"})

        import os
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
        # NOTE: no `finally: _cleanup_temp_file(...)` here anymore — the
        # file at file_path is the PERMANENT citation-viewer copy now, not
        # a temp upload, so ingestion success or failure never deletes it.

        container.history_service.update_file_status(int(file_id), "indexed", total_chunks_indexed)

        return {
            "status": "success",
            "total_chunks_indexed": total_chunks_indexed,
            "file_name": file_name,
            "file_id": file_id,
        }

    except Exception as e:
        traceback.print_exc()
        try:
            container.history_service.update_file_status(int(file_id), "failed")
        except Exception:
            pass
        return {"status": "failed", "detail": str(e)}
    finally:
        db.close()
