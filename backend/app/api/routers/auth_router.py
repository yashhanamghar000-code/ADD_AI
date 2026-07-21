from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_container, get_current_user
from app.api.schemas.auth_schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.container import Container
from app.core.exceptions import AuthenticationError, ValidationError
from app.infrastructure.db.models import UserModel

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, container: Container = Depends(get_container)):
    try:
        result = container.auth_service.register(payload.name, payload.email, payload.password)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"token": result.token, "user": result.user}


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, container: Container = Depends(get_container)):
    try:
        result = container.auth_service.login(payload.email, payload.password)
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return {"token": result.token, "user": result.user}


@router.get("/me", response_model=UserOut)
def me(current_user: UserModel = Depends(get_current_user)):
    return current_user


@router.post("/logout")
def logout():
    # Stateless JWT: nothing to invalidate server-side without a blocklist.
    # The frontend just deletes the token from local storage.
    return {"status": "ok"}
