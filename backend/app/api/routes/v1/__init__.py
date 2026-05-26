"""API v1 router aggregation."""
# ruff: noqa: I001 - Imports structured for Jinja2 template conditionals

from fastapi import APIRouter

from app.api.routes.v1 import health
from app.api.routes.v1 import admin_ratings, auth, users
from app.api.routes.v1 import sessions
from app.api.routes.v1 import conversations
from app.api.routes.v1 import admin_conversations
from app.api.routes.v1 import agent
from app.api.routes.v1 import rag
from app.api.routes.v1 import files
from app.api.routes.v1 import shared_documents

v1_router = APIRouter()

# Health check routes (no auth required)
v1_router.include_router(health.router, tags=["health"])

# Authentication routes
v1_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# User routes
v1_router.include_router(users.router, prefix="/users", tags=["users"])

# Admin routes
v1_router.include_router(admin_ratings.router, prefix="/admin/ratings", tags=["admin:ratings"])

# Session management routes
v1_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])

# Conversation routes (AI chat persistence)
v1_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])


# AI Agent routes
v1_router.include_router(agent.router, tags=["agent"])

# RAG routes
v1_router.include_router(rag.router, prefix="/rag", tags=["rag"])

# File upload/download routes
v1_router.include_router(files.router, tags=["files"])

# Shared documents (EFS cloud storage)
v1_router.include_router(
    shared_documents.router, prefix="/shared-documents", tags=["shared-documents"]
)

# Admin: conversation browser + user listing
v1_router.include_router(
    admin_conversations.router, prefix="/admin/conversations", tags=["admin-conversations"]
)
