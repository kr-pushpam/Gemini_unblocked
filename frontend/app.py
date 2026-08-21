"""
Streamlit main app — landing page and navigation hub.

Run with:
    streamlit run frontend/app.py --server.port 8501

Streamlit auto-discovers pages in the `pages/` subdirectory
and creates sidebar navigation from filenames.
"""

import streamlit as st

st.set_page_config(
    page_title="Gemini Unblocked",
    page_icon="🔓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🔓 Gemini Unblocked")
st.markdown(
    """
    Access Gemini multimodal capabilities through **Vertex AI** —
    bypassing direct API restrictions via your GCP project.

    ### Features

    | Page | What it does |
    |------|-------------|
    | 💬 **Chat** | Multi-turn streaming conversation |
    | 📄 **Documents** | Upload PDFs, images, spreadsheets for analysis |
    | 🎨 **Image Gen** | Generate images from text prompts (Imagen 3) |
    | 🔍 **Grounded Search** | Get answers backed by Google Search |

    ---

    Use the **sidebar** to navigate between features.
    """
)

# Sidebar — backend status check
with st.sidebar:
    st.markdown("### Status")
    import httpx
    import os

    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")

    try:
        resp = httpx.get(f"{backend_url}/health", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            st.success(f"✅ Backend connected")
            st.caption(f"Project: `{data['project']}`")
            st.caption(f"Model: `{data['model']}`")
            st.caption(f"Region: `{data['location']}`")
        else:
            st.error("❌ Backend returned error")
    except Exception:
        st.warning(
            "⚠️ Backend not reachable.\n\n"
            "Start it with:\n"
            "```\nuvicorn backend.main:app --port 8000\n```"
        )
