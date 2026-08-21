"""
🔍 Grounded Search page — factual answers backed by Google Search.

How grounding works:
1. You ask a question
2. Gemini formulates search queries
3. Google Search retrieves current web results
4. Gemini synthesizes an answer using those sources
5. Source URLs are returned for verification

This dramatically reduces hallucinations for factual questions
and gives you access to real-time information.
"""

import os

import httpx
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Grounded Search", page_icon="🔍", layout="wide")
st.title("🔍 Grounded Search")
st.markdown(
    "Ask questions and get answers **grounded with Google Search** — "
    "with source citations for verification."
)

# ─── Input ────────────────────────────────────────────────────────────────────

prompt = st.text_area(
    "Your question:",
    placeholder="What are the latest features announced for Google Cloud Run in 2024?",
    height=100,
)

col1, col2 = st.columns(2)
with col1:
    streaming = st.toggle("⚡ Stream response", value=False)
    st.caption("Note: source citations only available in non-streaming mode.")
with col2:
    search_btn = st.button("🔍 Search", type="primary", use_container_width=True)

# ─── Search ───────────────────────────────────────────────────────────────────

if prompt and search_btn:
    st.divider()

    if streaming:
        # Streaming — no citations available mid-stream
        st.markdown("### Response")
        placeholder = st.empty()
        full_response = ""

        try:
            with httpx.stream(
                "POST",
                f"{BACKEND_URL}/api/multimodal/grounded-search/stream",
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
        # Non-streaming — get full response with citations
        with st.spinner("Searching and generating..."):
            try:
                resp = httpx.post(
                    f"{BACKEND_URL}/api/multimodal/grounded-search",
                    data={"prompt": prompt},
                    timeout=120,
                )
                resp.raise_for_status()
                result = resp.json()

                st.markdown("### Response")
                st.markdown(result["response"])

                # Display source citations
                metadata = result.get("grounding_metadata")
                if metadata:
                    st.divider()
                    st.markdown("### 📚 Sources")

                    # Search queries used by the model
                    if metadata.get("search_queries"):
                        st.caption(
                            f"Search queries: {', '.join(metadata['search_queries'])}"
                        )

                    # Source links
                    chunks = metadata.get("grounding_chunks", [])
                    if chunks:
                        for i, chunk in enumerate(chunks, 1):
                            title = chunk.get("title", "Source")
                            uri = chunk.get("uri", "")
                            if uri:
                                st.markdown(f"{i}. [{title}]({uri})")
                            else:
                                st.markdown(f"{i}. {title}")
                    else:
                        st.caption("No source citations available for this response.")

                st.caption(f"Model: {result['model']}")

            except httpx.HTTPError as e:
                st.error(f"Error: {e}")

elif search_btn and not prompt:
    st.warning("Please enter a question.")

# ─── Examples ─────────────────────────────────────────────────────────────────

with st.expander("💡 Example queries (good for grounding)"):
    st.markdown("""
    - "What are the new features in Python 3.13?"
    - "Latest Google Cloud Run pricing changes"
    - "Compare React vs Vue.js in 2024"
    - "Current best practices for Kubernetes security"
    - "What happened in AI news this week?"
    """)
