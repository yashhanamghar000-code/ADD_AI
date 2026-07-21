"""
FULL FILE — replace your existing backend/app/infrastructure/db/models.py.
Only change: UploadedFileModel now has `file_path`, pointing at the
permanent copy of the original upload (used to reopen the PDF for the
citation viewer).

IMPORTANT — you already have a `uploaded_files` table in Postgres. Adding
a column to an existing SQLAlchemy model does NOT alter the live table by
itself (Base.metadata.create_all only creates tables that don't exist
yet). Run this once against your DB before starting the app:

    ALTER TABLE uploaded_files ADD COLUMN file_path VARCHAR;

(or drop/recreate the table in a throwaway dev DB, or wire up Alembic if
you don't have migrations yet.)
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.infrastructure.db.database import Base


class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversations = relationship("ConversationModel", back_populates="user", cascade="all, delete-orphan")


class ConversationModel(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, default="New Chat")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("UserModel", back_populates="conversations")
    messages = relationship("ChatMessageModel", back_populates="conversation", cascade="all, delete-orphan")
    files = relationship("UploadedFileModel", back_populates="conversation", cascade="all, delete-orphan")


class ChatMessageModel(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("ConversationModel", back_populates="messages")


class UploadedFileModel(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    file_name = Column(String, nullable=False)
    status = Column(String, default="processing")
    total_chunks_indexed = Column(Integer, default=0)
    # NEW: absolute/relative path to the permanently stored original file.
    file_path = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("ConversationModel", back_populates="files")
