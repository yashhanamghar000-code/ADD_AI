from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt

from app.core.interfaces.token_service import ITokenService


class JwtTokenService(ITokenService):

    def __init__(self, secret_key: str, algorithm: str, expire_minutes: int):
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._expire_minutes = expire_minutes

    def issue_token(self, user_id: int) -> str:
        expire = datetime.utcnow() + timedelta(minutes=self._expire_minutes)
        payload = {"sub": str(user_id), "exp": expire}
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def verify_token(self, token: str) -> Optional[int]:
        try:
            payload = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
            user_id = payload.get("sub")
            return int(user_id) if user_id is not None else None
        except (JWTError, ValueError, TypeError):
            return None
