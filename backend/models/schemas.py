"""
Pydantic models for request/response validation.

FastAPI uses these to:
1. Validate incoming request bodies (reject malformed data)
2. Serialize outgoing responses (consistent JSON shape)
3. Auto-generate OpenAPI docs (try /docs in your browser)
"""

from pydantic import BaseModel


# ─── Chat ─────────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    """Incoming chat message."""
    message: str
    session_id: str | None = None  # None = create new session


class ChatResponse(BaseModel):
    """Non-streaming chat response."""
    response: str
    session_id: str


# ─── Multimodal ───────────────────────────────────────────────────────────────


class ImageAnalysisResponse(BaseModel):
    """Response from image/document analysis."""
    response: str
    model: str
    file_name: str | None = None
    mime_type: str | None = None


# ─── Sessions ─────────────────────────────────────────────────────────────────


class SessionListResponse(BaseModel):
    """List of chat sessions."""
    sessions: list[dict]
