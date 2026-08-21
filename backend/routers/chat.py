"""
Chat router — multi-turn conversation with streaming support.

Two main endpoints:
- POST /api/chat/send     → Full response (waits for completion)
- POST /api/chat/stream   → SSE stream (tokens arrive in real-time)

Both persist messages to Firestore for history.

How SSE (Server-Sent Events) works:
1. Client opens a long-lived HTTP connection
2. Server sends "data: chunk\n\n" as each token arrives
3. Client renders tokens incrementally
4. Server sends "event: done" when finished
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.models.schemas import ChatRequest, ChatResponse, SessionListResponse
from backend.services import gemini_service, firestore_service

router = APIRouter()


# ─── Send (non-streaming) ─────────────────────────────────────────────────────


@router.post("/send", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """Send a message, get complete response. Good for programmatic use."""

    # Create or reuse session
    session_id = request.session_id
    if not session_id:
        session_id = firestore_service.create_session()

    session = firestore_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = session.get("messages", [])

    # Generate — with history if we have prior messages
    if messages:
        response_text = gemini_service.generate_with_history(
            messages, request.message
        )
    else:
        response_text = gemini_service.generate_text(request.message)

    # Persist both sides of the conversation
    firestore_service.add_message(session_id, "user", request.message)
    firestore_service.add_message(session_id, "model", response_text)

    return ChatResponse(response=response_text, session_id=session_id)


# ─── Stream (SSE) ─────────────────────────────────────────────────────────────


@router.post("/stream")
async def stream_message(request: ChatRequest):
    """Stream response via Server-Sent Events. Used by the Streamlit frontend."""

    session_id = request.session_id
    if not session_id:
        session_id = firestore_service.create_session()

    session = firestore_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = session.get("messages", [])

    # Save user message immediately (response saved after streaming completes)
    firestore_service.add_message(session_id, "user", request.message)

    def event_stream():
        full_response = ""

        # Choose streaming method based on history
        if messages:
            generator = gemini_service.stream_with_history(messages, request.message)
        else:
            generator = gemini_service.stream_text(request.message)

        for chunk in generator:
            full_response += chunk
            # SSE format: "data: <payload>\n\n"
            yield f"data: {chunk}\n\n"

        # Save complete response to Firestore
        firestore_service.add_message(session_id, "model", full_response)

        # Signal completion with session_id
        yield f"event: done\ndata: {session_id}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Session-Id": session_id,
        },
    )


# ─── Session Management ───────────────────────────────────────────────────────


@router.post("/new-session")
async def create_session():
    """Create a new empty chat session."""
    session_id = firestore_service.create_session()
    return {"session_id": session_id}


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions():
    """List recent chat sessions (newest first)."""
    sessions = firestore_service.list_sessions()
    return SessionListResponse(sessions=sessions)


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get a specific session with all messages."""
    session = firestore_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, **session}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session."""
    firestore_service.delete_session(session_id)
    return {"status": "deleted"}
