from typing import Optional

from sqlalchemy.orm import Session

from app.core.interfaces.repositories import IUserRepository
from app.infrastructure.db.models import UserModel


class SqlAlchemyUserRepository(IUserRepository):
    """Concrete Postgres/SQLAlchemy implementation of IUserRepository.
    Swappable behind the interface — a test suite can substitute an
    in-memory fake without touching AuthService."""

    def __init__(self, db: Session):
        self._db = db

    def get_by_email(self, email: str) -> Optional[UserModel]:
        return self._db.query(UserModel).filter(UserModel.email == email).first()

    def get_by_id(self, user_id: int) -> Optional[UserModel]:
        return self._db.query(UserModel).filter(UserModel.id == user_id).first()

    def create(self, name: str, email: str, hashed_password: str) -> UserModel:
        user = UserModel(name=name, email=email, hashed_password=hashed_password)
        self._db.add(user)
        self._db.commit()
        self._db.refresh(user)
        return user
