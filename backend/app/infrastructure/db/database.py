"""SQLAlchemy engine/session factory. This is the ONLY module in the whole
codebase that knows the persistence layer is Postgres via SQLAlchemy —
everything above it (repositories) is what services actually depend on."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config.settings import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: one DB session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
