from passlib.context import CryptContext

from app.core.interfaces.password_hasher import IPasswordHasher


class BcryptPasswordHasher(IPasswordHasher):
    """Swappable behind IPasswordHasher — e.g. argon2 later needs only a
    new class here, no changes anywhere that calls it."""

    def __init__(self):
        self._ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash(self, plain_password: str) -> str:
        return self._ctx.hash(plain_password)

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        return self._ctx.verify(plain_password, hashed_password)
