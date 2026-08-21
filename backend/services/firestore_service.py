"""
Firestore service for persisting chat sessions.

Why Firestore?
- Serverless (no database to manage)
- Real-time capable
- Scales automatically
- Free tier generous for dev/testing
- Native GCP auth (same credentials as Vertex AI)

Data model:
    Collection: "chat_sessions"
    Document ID: UUID
    Fields:
        - created_at: ISO timestamp
        - updated_at: ISO timestamp
        - messages: array of {role, content, timestamp}
"""

import uuid
from datetime import datetime, timezone

from google.cloud import firestore

from backend.config import settings

_db = None

COLLECTION = "chat_sessions"


def _get_db() -> firestore.Client:
    """Lazy-initialize Firestore client (reuses connection)."""
    global _db
    if _db is None:
        _db = firestore.Client(
            project=settings.GCP_PROJECT_ID,
            database=settings.FIRESTORE_DATABASE,
        )
    return _db


# ─── Session CRUD ─────────────────────────────────────────────────────────────


def create_session() -> str:
    """Create a new empty chat session. Returns the session ID."""
    db = _get_db()
    session_id = str(uuid.uuid4())
    db.collection(COLLECTION).document(session_id).set({
        "created_at": datetime.now(timezone.utc).isoformat(),
        "messages": [],
    })
    return session_id


def get_session(session_id: str) -> dict | None:
    """Fetch a session by ID. Returns None if not found."""
    db = _get_db()
    doc = db.collection(COLLECTION).document(session_id).get()
    if doc.exists:
        return doc.to_dict()
    return None


def add_message(session_id: str, role: str, content: str):
    """Append a message to an existing session."""
    db = _get_db()
    doc_ref = db.collection(COLLECTION).document(session_id)
    doc_ref.update({
        "messages": firestore.ArrayUnion([{
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })


def list_sessions(limit: int = 20) -> list[dict]:
    """List recent sessions, newest first."""
    db = _get_db()
    docs = (
        db.collection(COLLECTION)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def delete_session(session_id: str):
    """Delete a session permanently."""
    db = _get_db()
    db.collection(COLLECTION).document(session_id).delete()
