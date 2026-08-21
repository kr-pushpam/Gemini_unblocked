"""
💬 Chat page — multi-turn streaming conversation with Gemini.
"""

import os

import httpx
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Chat", page_icon="💬", layout="wide")
st.title("💬 Chat with Gemini")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = None


def create_new_session():
    try:
        resp = httpx.post(f"{BACKEND_URL}/api/chat/new-session", timeout=10)
        resp.raise_for_status()
        return resp.json()["session_id"]
    except httpx.HTTPError as e:
        st.error(f"Failed to create session: {e}")
        return None


def load_session_from_backend(session_id: str):
    try:
        resp = httpx.get(f"{BACKEND_URL}/api/chat/sessions/{session_id}", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        messages = data.get("messages", [])
        display_messages = []
        for msg in messages:
            role = "assistant" if msg["role"] == "model" else msg["role"]
            display_messages.append({"role": role, "content": msg["content"]})
        return display_messages
    except httpx.HTTPError:
        return []


if st.session_state.session_id and not st.session_state.messages:
    st.session_state.messages = load_session_from_backend(st.session_state.session_id)

# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### Chat Controls")

    if st.button("🆕 New Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.session_id = None
        st.rerun()

    st.divider()
    streaming_mode = st.toggle("⚡ Streaming", value=True)

    st.divider()
    st.markdown("### Recent Chats")

    try:
        resp = httpx.get(f"{BACKEND_URL}/api/chat/sessions", timeout=5)
        resp.raise_for_status()
        sessions = resp.json().get("sessions", [])

        if sessions:
            for session in sessions[:10]:
                sid = session.get("id", "")
                messages = session.get("messages", [])
                label = "Empty chat"
                for msg in messages:
                    if msg.get("role") == "user":
                        label = msg["content"][:35].replace("[📎", "📎")
                        if len(msg["content"]) > 35:
                            label += "..."
                        break

                is_active = sid == st.session_state.session_id
                btn_label = f"{'▶ ' if is_active else ''}{label}"

                if st.button(btn_label, key=f"session_{sid}", use_container_width=True):
                    st.session_state.session_id = sid
                    st.session_state.messages = load_session_from_backend(sid)
                    st.rerun()
        else:
            st.caption("No previous chats yet.")
    except httpx.HTTPError:
        st.caption("Could not load sessions.")

    if st.session_state.session_id:
        st.divider()
        st.caption(f"Session: `{st.session_state.session_id[:8]}...`")

# ─── Chat History ─────────────────────────────────────────────────────────────

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ─── Input Area (bottom) ──────────────────────────────────────────────────────
# File uploader + chat input together at the bottom

col_file, col_info = st.columns([3, 1])
with col_file:
    uploaded_file = st.file_uploader(
        "attach",
        type=["pdf", "png", "jpg", "jpeg", "gif", "webp", "txt", "csv"],
        key="chat_file_upload",
        label_visibility="collapsed",
    )
with col_info:
    if uploaded_file:
        st.caption(f"📎 {uploaded_file.name}")

if prompt := st.chat_input("Type your message..."):
    if not st.session_state.session_id:
        st.session_state.session_id = create_new_session()

    # ── With file ─────────────────────────────────────────────────────────────
    if uploaded_file:
        user_display = f"📎 *{uploaded_file.name}*\n\n{prompt}"
        st.session_state.messages.append({"role": "user", "content": user_display})
        with st.chat_message("user"):
            st.markdown(user_display)

        with st.chat_message("assistant"):
            with st.spinner("Analyzing file..."):
                try:
                    resp = httpx.post(
                        f"{BACKEND_URL}/api/chat/send-with-file",
                        files={"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)},
                        data={"message": prompt, "session_id": st.session_state.session_id},
                        timeout=120,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    full_response = data["response"]
                    st.markdown(full_response)
                except httpx.HTTPStatusError as e:
                    error_detail = e.response.text[:200] if e.response else str(e)
                    st.error(f"Error: {error_detail}")
                    full_response = f"Error: {error_detail}"
                except httpx.HTTPError as e:
                    st.error(f"Error: {e}")
                    full_response = f"Error: {e}"

        st.session_state.messages.append({"role": "assistant", "content": full_response})

    # ── Text only ─────────────────────────────────────────────────────────────
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            if streaming_mode:
                placeholder = st.empty()
                full_response = ""
                try:
                    with httpx.stream(
                        "POST",
                        f"{BACKEND_URL}/api/chat/stream",
                        json={"message": prompt, "session_id": st.session_state.session_id},
                        timeout=120,
                    ) as response:
                        response.raise_for_status()
                        for line in response.iter_lines():
                            if line.startswith("data: "):
                                full_response += line[6:]
                                placeholder.markdown(full_response + "▌")
                            elif line.startswith("event: done"):
                                break
                    placeholder.markdown(full_response)
                except httpx.HTTPError as e:
                    st.error(f"Error: {e}")
                    full_response = f"Error: {e}"
            else:
                with st.spinner("Thinking..."):
                    try:
                        resp = httpx.post(
                            f"{BACKEND_URL}/api/chat/send",
                            json={"message": prompt, "session_id": st.session_state.session_id},
                            timeout=120,
                        )
                        resp.raise_for_status()
                        data = resp.json()
                        full_response = data["response"]
                        st.markdown(full_response)
                    except httpx.HTTPError as e:
                        st.error(f"Error: {e}")
                        full_response = f"Error: {e}"

        st.session_state.messages.append({"role": "assistant", "content": full_response})
