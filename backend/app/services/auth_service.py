"""
Application/use-case layer: AuthService only depends on INTERFACES
(IUserRepository, IPasswordHasher, ITokenService) — never on SQLAlchemy,
passlib, or python-jose directly. That's Dependency Inversion: business
rules don't know or care which concrete technology implements them, so
swapping bcrypt for argon2, or Postgres for something else, never touches
this file.
"""
from dataclasses import dataclass
from typing import Any

from app.core.exceptions import AuthenticationError, ValidationError
from app.core.interfaces.password_hasher import IPasswordHasher
from app.core.interfaces.repositories import IUserRepository
from app.core.interfaces.token_service import ITokenService


@dataclass
class AuthResult:
    token: str
    user: Any


class AuthService:

    def __init__(self, user_repository: IUserRepository, password_hasher: IPasswordHasher, token_service: ITokenService):
        self._users = user_repository
        self._hasher = password_hasher
        self._tokens = token_service

    def register(self, name: str, email: str, password: str) -> AuthResult:
        if self._users.get_by_email(email):
            raise ValidationError("Email already registered")

        user = self._users.create(name=name, email=email, hashed_password=self._hasher.hash(password))
        token = self._tokens.issue_token(user.id)
        return AuthResult(token=token, user=user)

    def login(self, email: str, password: str) -> AuthResult:
        user = self._users.get_by_email(email)
        if not user or not self._hasher.verify(password, user.hashed_password):
            raise AuthenticationError("Invalid email or password")

        token = self._tokens.issue_token(user.id)
        return AuthResult(token=token, user=user)

    def get_current_user(self, token: str) -> Any:
        user_id = self._tokens.verify_token(token)
        if user_id is None:
            raise AuthenticationError("Invalid or expired token")

        user = self._users.get_by_id(user_id)
        if user is None:
            raise AuthenticationError("User not found")
        return user
