"""
FastAPI application entry point.

This is the file uvicorn points at:
    uvicorn backend.main:app --reload --port 8000

It wires together:
- CORS middleware (so Streamlit frontend can talk to the API)
- All routers (health, chat, multimodal)
- Config validation (fails fast if .env isn't configured)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.routers import health, chat, multimodal

# Validate config at startup — crash early if GCP_PROJECT_ID not set
settings.validate()

app = FastAPI(
    title="Gemini Unblocked API",
    description="Access Gemini multimodal LLMs via Vertex AI",
    version="0.1.0",
)

# Allow frontend (Streamlit) to call the API from any origin in dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router, tags=["Health"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(multimodal.router, prefix="/api/multimodal", tags=["Multimodal"])
