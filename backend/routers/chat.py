"""
Chat router — multi-turn conversation with streaming and file attachments.
"""

from fastapi import APIRouter, HTTPException, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from backend.models.schemas import ChatRequest, ChatResponse, SessionListResponse
from backend.services import gemini_service, firestore_service

router = APIRouter()


@router.post("/send", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    session_id = request.session_id
    if not session_id:
        session_id = firestore_service.create_session()

    session = firestore_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = session.get("messages", [])

    if messages:
        response_text = gemini_service.generate_with_history(messages, request.message)
    else:
        response_text = gemini_service.generate_text(request.message)

    firestore_service.add_message(session_id, "user", request.message)
    firestore_service.add_message(session_id, "model", response_text)

    return ChatResponse(response=response_text, session_id=session_id)


@router.post("/stream")
async def stream_message(request: ChatRequest):
    session_id = request.session_id
    if not session_id:
        session_id = firestore_service.create_session()

    session = firestore_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = session.get("messages", [])
    firestore_service.add_message(session_id, "user", request.message)

    def event_stream():
        full_response = ""
        if messages:
            generator = gemini_service.stream_with_history(messages, request.message)
        else:
            generator = gemini_service.stream_text(request.message)

        for chunk in generator:
            full_response += chunk
            yield f"data: {chunk}\n\n"

        firestore_service.add_message(session_id, "model", full_response)
        yield f"event: done\ndata: {session_id}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Session-Id": session_id},
    )


@router.post("/send-with-file")
async def send_with_file(
    file: UploadFile = File(...),
    message: str = Form("Describe this file."),
    session_id: str = Form(None),
):
    if not session_id:
        session_id = firestore_service.create_session()

    session = firestore_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    contents = await file.read()
    mime_type = file.content_type or "application/octet-stream"

    if mime_type.startswith("image/"):
        response_text = gemini_service.analyze_image(contents, mime_type, message)
    else:
        response_text = gemini_service.analyze_document(contents, mime_type, message)

    user_msg = f"[📎 {file.filename}] {message}"
    firestore_service.add_message(session_id, "user", user_msg)
    firestore_service.add_message(session_id, "model", response_text)

    return {"response": response_text, "session_id": session_id, "file_name": file.filename}


@router.post("/new-session")
async def create_session():
    session_id = firestore_service.create_session()
    return {"session_id": session_id}


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions():
    sessions = firestore_service.list_sessions()
    return SessionListResponse(sessions=sessions)


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    session = firestore_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, **session}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    firestore_service.delete_session(session_id)
    return {"status": "deleted"}
