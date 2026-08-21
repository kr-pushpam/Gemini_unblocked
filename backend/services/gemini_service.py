"""
Vertex AI Gemini service.

This is the core LLM layer. All Gemini interactions go through here:
- Text generation (single prompt)
- Multi-turn chat (with history)
- Multimodal (image + text, document + text)
- Streaming (yields chunks as they arrive)
- Google Search grounding (factual answers with citations)

IMPORTANT: Vertex AI SDK is synchronous. We use sync generators for streaming
and let FastAPI's StreamingResponse handle them in a thread.
"""

from collections.abc import Generator
from typing import Any

import vertexai
from vertexai.generative_models import (
    Content,
    GenerativeModel,
    Part,
    Tool,
    grounding,
)

from backend.config import settings

# ─── Initialization ───────────────────────────────────────────────────────────

_initialized = False


def _ensure_init():
    """Initialize Vertex AI SDK once. Uses ADC/WIF credentials automatically."""
    global _initialized
    if not _initialized:
        vertexai.init(
            project=settings.GCP_PROJECT_ID,
            location=settings.GCP_LOCATION,
        )
        _initialized = True


def get_model(model_name: str | None = None, **kwargs) -> GenerativeModel:
    """Get a GenerativeModel instance (initializes SDK if needed)."""
    _ensure_init()
    return GenerativeModel(model_name or settings.MODEL_NAME, **kwargs)


def _build_history(messages: list[dict]) -> list[Content]:
    """
    Convert our message format to Vertex AI Content objects.

    Our format: [{"role": "user", "content": "hello"}, {"role": "model", "content": "hi"}]
    Vertex AI expects: [Content(role="user", parts=[Part.from_text("hello")]), ...]
    """
    history = []
    for msg in messages:
        history.append(
            Content(
                role=msg["role"],
                parts=[Part.from_text(msg["content"])],
            )
        )
    return history


# ─── Text Generation ──────────────────────────────────────────────────────────


def generate_text(prompt: str) -> str:
    """Simple single-turn text generation."""
    model = get_model()
    response = model.generate_content(prompt)
    return response.text


def generate_with_history(messages: list[dict], new_message: str) -> str:
    """
    Multi-turn generation with conversation history.

    messages: list of {"role": "user"|"model", "content": "..."}
    new_message: the latest user message
    """
    model = get_model()
    history = _build_history(messages)
    chat = model.start_chat(history=history)
    response = chat.send_message(new_message)
    return response.text


# ─── Streaming ────────────────────────────────────────────────────────────────


def stream_text(prompt: str) -> Generator[str, None, None]:
    """
    Stream text response chunk-by-chunk (synchronous generator).

    Why streaming? The frontend can display tokens as they arrive,
    giving the user immediate feedback instead of waiting 5-10s.
    """
    model = get_model()
    response = model.generate_content(prompt, stream=True)
    for chunk in response:
        if chunk.text:
            yield chunk.text


def stream_with_history(
    messages: list[dict], new_message: str
) -> Generator[str, None, None]:
    """Stream response within an ongoing conversation."""
    model = get_model()
    history = _build_history(messages)
    chat = model.start_chat(history=history)
    response = chat.send_message(new_message, stream=True)
    for chunk in response:
        if chunk.text:
            yield chunk.text


# ─── Multimodal (Image / Document) ───────────────────────────────────────────


def analyze_image(image_bytes: bytes, mime_type: str, prompt: str) -> str:
    """
    Analyze an image with a text prompt.

    Gemini is natively multimodal — you pass [image, text] and it
    understands both together. No separate vision model needed.
    """
    model = get_model()
    image_part = Part.from_data(image_bytes, mime_type=mime_type)
    response = model.generate_content([image_part, prompt])
    return response.text


def analyze_document(doc_bytes: bytes, mime_type: str, prompt: str) -> str:
    """
    Analyze a PDF or document file with a text prompt.

    Gemini can read PDFs directly — it extracts text and layout,
    understands tables, charts, and images within the document.
    """
    model = get_model()
    doc_part = Part.from_data(doc_bytes, mime_type=mime_type)
    response = model.generate_content([doc_part, prompt])
    return response.text


def stream_multimodal(
    file_bytes: bytes, mime_type: str, prompt: str
) -> Generator[str, None, None]:
    """Stream analysis of any file (image or document)."""
    model = get_model()
    file_part = Part.from_data(file_bytes, mime_type=mime_type)
    response = model.generate_content([file_part, prompt], stream=True)
    for chunk in response:
        if chunk.text:
            yield chunk.text


# ─── Google Search Grounding ──────────────────────────────────────────────────


def generate_grounded(prompt: str) -> dict[str, Any]:
    """
    Generate a response grounded with Google Search.

    What this does:
    1. Gemini formulates search queries from your prompt
    2. Google Search retrieves relevant results
    3. Gemini synthesizes an answer citing those sources

    This reduces hallucinations for factual/current questions.
    """
    _ensure_init()

    google_search_tool = Tool.from_google_search_retrieval(
        grounding.GoogleSearchRetrieval()
    )

    model = GenerativeModel(
        settings.MODEL_NAME,
        tools=[google_search_tool],
    )

    response = model.generate_content(prompt)

    # Extract source citations if available
    grounding_metadata = None
    if response.candidates and response.candidates[0].grounding_metadata:
        metadata = response.candidates[0].grounding_metadata
        grounding_metadata = {
            "search_queries": [
                q.text for q in (metadata.web_search_queries or [])
            ],
            "grounding_chunks": [
                {
                    "title": c.web.title if c.web else "",
                    "uri": c.web.uri if c.web else "",
                }
                for c in (metadata.grounding_chunks or [])
            ],
        }

    return {
        "response": response.text,
        "grounding_metadata": grounding_metadata,
    }


def stream_grounded(prompt: str) -> Generator[str, None, None]:
    """Stream a grounded response (citations only available after full response)."""
    _ensure_init()

    google_search_tool = Tool.from_google_search_retrieval(
        grounding.GoogleSearchRetrieval()
    )

    model = GenerativeModel(
        settings.MODEL_NAME,
        tools=[google_search_tool],
    )

    response = model.generate_content(prompt, stream=True)
    for chunk in response:
        if chunk.text:
            yield chunk.text
