"""
FastAPI application entry point. Deliberately thin: it only wires
middleware and routers together. All business logic lives in services/,
all persistence in infrastructure/ — this file has exactly one
responsibility, assembling the HTTP app (Single Responsibility Principle
applied at the module level).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers.auth_router import router as auth_router
from app.api.routers.chat_router import router as chat_router
from app.api.routers.conversation_router import router as conversation_router
from app.api.routers.document_router import router as document_router
from app.api.routers.health_router import router as health_router
from app.api.routers.session_router import router as session_router
from app.api.routers.upload_router import router as upload_router
from app.infrastructure.db.database import Base, engine

app = FastAPI(title="AUDITO AI Multiuser RAG Engine")

Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(conversation_router)
app.include_router(upload_router)
app.include_router(chat_router)
app.include_router(session_router)
app.include_router(document_router)
