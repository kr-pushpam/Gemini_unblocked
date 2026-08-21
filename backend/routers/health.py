"""
Health check endpoint.

Used by:
- Cloud Run to confirm the container is alive
- Frontend to verify backend is reachable
- You, to quickly test if things are wired up
"""

from fastapi import APIRouter
from backend.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """Returns service status and current config (non-sensitive)."""
    return {
        "status": "healthy",
        "service": "gemini-unblocked-api",
        "project": settings.GCP_PROJECT_ID,
        "location": settings.GCP_LOCATION,
        "model": settings.MODEL_NAME,
    }
