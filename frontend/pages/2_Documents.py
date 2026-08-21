"""
📄 Document Analysis page — upload files for Gemini to analyze.

Supported formats:
- PDF (extracts text, tables, images within)
- Images (JPEG, PNG, GIF, WebP)
- Text files (TXT, CSV, HTML)
- Office docs (DOCX, XLSX)

Gemini processes the file content natively — no OCR or parsing library needed.
The model sees the actual rendered content, including charts and layouts.
"""

import os

import httpx
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Documents", page_icon="📄", layout="wide")
st.title("📄 Document & File Analysis")
st.markdown("Upload any file — Gemini reads PDFs, images, spreadsheets, and more natively.")

# ─── File Upload ──────────────────────────────────────────────────────────────

uploaded_file = st.file_uploader(
    "Choose a file",
    type=["pdf", "png", "jpg", "jpeg", "gif", "webp", "txt", "csv", "html", "docx", "xlsx"],
    help="Max 20MB. Gemini processes the file content directly.",
)

# ─── Prompt ───────────────────────────────────────────────────────────────────

prompt = st.text_area(
    "What would you like to know about this file?",
    value="Summarize this document and extract the key points.",
    height=100,
)

# ─── Controls ─────────────────────────────────────────────────────────────────

col1, col2 = st.columns(2)
with col1:
    streaming = st.toggle("⚡ Stream response", value=True)
with col2:
    analyze_btn = st.button("🔍 Analyze", type="primary", use_container_width=True)

# ─── Analysis ─────────────────────────────────────────────────────────────────

if uploaded_file and analyze_btn:
    st.divider()

    # File info
    file_size_kb = uploaded_file.size / 1024
    st.caption(f"📎 {uploaded_file.name} ({uploaded_file.type}, {file_size_kb:.1f} KB)")

    if streaming:
        st.markdown("### Response")
        placeholder = st.empty()
        full_response = ""

        try:
            with httpx.stream(
                "POST",
                f"{BACKEND_URL}/api/multimodal/analyze-file/stream",
                files={"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)},
                data={"prompt": prompt},
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

    else:
        with st.spinner("Analyzing..."):
            try:
                resp = httpx.post(
                    f"{BACKEND_URL}/api/multimodal/analyze-file",
                    files={"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)},
                    data={"prompt": prompt},
                    timeout=120,
                )
                resp.raise_for_status()
                result = resp.json()

                st.markdown("### Response")
                st.markdown(result["response"])
                st.caption(f"Model: {result['model']}")

            except httpx.HTTPError as e:
                st.error(f"Error: {e}")

elif not uploaded_file and analyze_btn:
    st.warning("Please upload a file first.")
