"""
💬 Chat page — multi-turn streaming conversation with Gemini.

How it works:
1. User types a message
2. Frontend sends POST to /api/chat/stream
3. Backend streams SSE events (token by token)
4. Frontend renders tokens as they arrive (typewriter effect)
5. Both user message and full response are saved to Firestore
"""

import os

import httpx
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Chat", page_icon="💬", layout="wide")
st.title("💬 Chat with Gemini")

# ─── Session State ────────────────────────────────────────────────────────────
# Streamlit re-runs the script on every interaction.
# session_state persists data across re-runs.

if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = None


def create_new_session():
    """Ask backend to create a new Firestore session."""
    try:
        resp = httpx.post(f"{BACKEND_URL}/api/chat/new-session", timeout=10)
        resp.raise_for_status()
        return resp.json()["session_id"]
    except httpx.HTTPError as e:
        st.error(f"Failed to create session: {e}")
        return None


# ─── Sidebar Controls ─────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### Chat Controls")

    if st.button("🆕 New Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.session_id = None
        st.rerun()

    st.divider()
    streaming_mode = st.toggle("⚡ Streaming", value=True)
    st.caption("Shows tokens as they arrive vs. waiting for full response.")

    if st.session_state.session_id:
        st.divider()
        st.caption(f"Session: `{st.session_state.session_id[:8]}...`")


# ─── Chat History Display ─────────────────────────────────────────────────────

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# ─── Chat Input ───────────────────────────────────────────────────────────────

if prompt := st.chat_input("Ask Gemini anything..."):
    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Ensure we have a backend session
    if not st.session_state.session_id:
        st.session_state.session_id = create_new_session()

    # Generate response
    with st.chat_message("assistant"):
        if streaming_mode:
            # ── Streaming path ──
            placeholder = st.empty()
            full_response = ""

            try:
                with httpx.stream(
                    "POST",
                    f"{BACKEND_URL}/api/chat/stream",
                    json={
                        "message": prompt,
                        "session_id": st.session_state.session_id,
                    },
                    timeout=120,
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if line.startswith("data: "):
                            chunk = line[6:]
                            full_response += chunk
                            placeholder.markdown(full_response + "▌")
                        elif line.startswith("event: done"):
                            break

                placeholder.markdown(full_response)

            except httpx.HTTPError as e:
                st.error(f"Error: {e}")
                full_response = f"Error: {e}"
        else:
            # ── Non-streaming path ──
            with st.spinner("Thinking..."):
                try:
                    resp = httpx.post(
                        f"{BACKEND_URL}/api/chat/send",
                        json={
                            "message": prompt,
                            "session_id": st.session_state.session_id,
                        },
                        timeout=120,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    full_response = data["response"]
                    st.session_state.session_id = data["session_id"]
                    st.markdown(full_response)

                except httpx.HTTPError as e:
                    st.error(f"Error: {e}")
                    full_response = f"Error: {e}"

    st.session_state.messages.append({"role": "assistant", "content": full_response})
