"""
FastAPI dependency wiring. This is the thin seam between the web framework
and the composition root (app.container) — routers depend on these
functions, never on concrete service classes directly, so the same
services/ layer could sit behind a different web framework unchanged.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.container import Container, build_container
from app.core.exceptions import AuthenticationError
from app.infrastructure.db.database import get_db
from app.infrastructure.db.models import UserModel

bearer_scheme = HTTPBearer()


def get_container(db: Session = Depends(get_db)) -> Container:
    return build_container(db)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    container: Container = Depends(get_container),
) -> UserModel:
    try:
        return container.auth_service.get_current_user(credentials.credentials)
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
