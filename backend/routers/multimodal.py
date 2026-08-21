"""
Multimodal router — file analysis, image generation, grounded search.

Endpoints:
- POST /api/multimodal/analyze-file         → Analyze image/PDF/document
- POST /api/multimodal/analyze-file/stream   → Same but streaming
- POST /api/multimodal/generate-image        → Text-to-image via Imagen 3
- POST /api/multimodal/grounded-search       → Gemini + Google Search
- POST /api/multimodal/grounded-search/stream→ Same but streaming
"""

from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import StreamingResponse

from backend.config import settings
from backend.services import gemini_service, imagen_service

router = APIRouter()

# Supported MIME types — Gemini can handle all of these directly
SUPPORTED_TYPES = {
    # Images
    "image/jpeg", "image/png", "image/gif", "image/webp",
    # Documents
    "application/pdf",
    "text/plain", "text/html", "text/csv",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


# ─── File / Document Analysis ─────────────────────────────────────────────────


@router.post("/analyze-file")
async def analyze_file(
    file: UploadFile = File(...),
    prompt: str = Form("Analyze this file and provide key insights."),
):
    """Upload any supported file and get Gemini's analysis."""
    contents = await file.read()
    mime_type = file.content_type or "application/octet-stream"

    if mime_type not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": f"Unsupported file type: {mime_type}",
                "supported": sorted(SUPPORTED_TYPES),
            },
        )

    # Gemini handles images and documents through the same API
    if mime_type.startswith("image/"):
        response_text = await gemini_service.analyze_image(contents, mime_type, prompt)
    else:
        response_text = await gemini_service.analyze_document(contents, mime_type, prompt)

    return {
        "response": response_text,
        "model": settings.MODEL_NAME,
        "file_name": file.filename,
        "mime_type": mime_type,
    }


@router.post("/analyze-file/stream")
async def stream_analyze_file(
    file: UploadFile = File(...),
    prompt: str = Form("Analyze this file and provide key insights."),
):
    """Upload a file and stream the analysis response."""
    contents = await file.read()
    mime_type = file.content_type or "application/octet-stream"

    if mime_type not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {mime_type}",
        )

    async def event_stream():
        async for chunk in gemini_service.stream_multimodal(contents, mime_type, prompt):
            yield f"data: {chunk}\n\n"
        yield "event: done\ndata: complete\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ─── Image Generation (Imagen 3) ──────────────────────────────────────────────


@router.post("/generate-image")
async def generate_image(
    prompt: str = Form(...),
    number_of_images: int = Form(1),
    aspect_ratio: str = Form("1:1"),
):
    """
    Generate images from a text prompt using Imagen 3.

    Returns base64-encoded PNG images that the frontend can display directly.
    """
    # Validate inputs
    if number_of_images < 1 or number_of_images > 4:
        raise HTTPException(status_code=400, detail="number_of_images must be 1-4")

    valid_ratios = {"1:1", "16:9", "9:16", "4:3", "3:4"}
    if aspect_ratio not in valid_ratios:
        raise HTTPException(
            status_code=400,
            detail=f"aspect_ratio must be one of: {sorted(valid_ratios)}",
        )

    images = await imagen_service.generate_image(
        prompt=prompt,
        number_of_images=number_of_images,
        aspect_ratio=aspect_ratio,
    )

    return {
        "images": images,
        "prompt": prompt,
        "model": "imagen-3.0-generate-002",
        "count": len(images),
    }


# ─── Google Search Grounding ──────────────────────────────────────────────────


@router.post("/grounded-search")
async def grounded_search(prompt: str = Form(...)):
    """
    Get an answer grounded with Google Search results.

    Returns the response text plus source citations (URLs and titles).
    """
    result = await gemini_service.generate_grounded(prompt)

    return {
        "response": result["response"],
        "grounding_metadata": result["grounding_metadata"],
        "model": settings.MODEL_NAME,
    }


@router.post("/grounded-search/stream")
async def stream_grounded_search(prompt: str = Form(...)):
    """Stream a grounded response (note: citations available only after full response)."""

    async def event_stream():
        async for chunk in gemini_service.stream_grounded(prompt):
            yield f"data: {chunk}\n\n"
        yield "event: done\ndata: complete\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
