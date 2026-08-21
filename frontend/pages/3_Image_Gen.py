"""
🎨 Image Generation page — create images from text using Imagen 3.

Imagen 3 is Google's text-to-image model (separate from Gemini).
It runs on Vertex AI and supports:
- Photorealistic and artistic styles
- Multiple aspect ratios
- Up to 4 images per prompt
- Safety filtering built-in
"""

import base64
import os

import httpx
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Image Generation", page_icon="🎨", layout="wide")
st.title("🎨 Image Generation")
st.markdown("Generate images from text prompts using **Imagen 3** on Vertex AI.")

# ─── Input ────────────────────────────────────────────────────────────────────

prompt = st.text_area(
    "Describe the image you want:",
    placeholder="A cozy coffee shop interior with warm lighting, watercolor style",
    height=100,
)

col1, col2, col3 = st.columns(3)
with col1:
    num_images = st.selectbox("Images", [1, 2, 3, 4], index=0)
with col2:
    aspect_ratio = st.selectbox(
        "Aspect ratio",
        ["1:1", "16:9", "9:16", "4:3", "3:4"],
        index=0,
    )
with col3:
    generate_btn = st.button("🖼️ Generate", type="primary", use_container_width=True)

# ─── Generation ───────────────────────────────────────────────────────────────

if prompt and generate_btn:
    st.divider()

    with st.spinner(f"Generating {num_images} image(s)... (10-30 seconds)"):
        try:
            resp = httpx.post(
                f"{BACKEND_URL}/api/multimodal/generate-image",
                data={
                    "prompt": prompt,
                    "number_of_images": num_images,
                    "aspect_ratio": aspect_ratio,
                },
                timeout=120,
            )
            resp.raise_for_status()
            result = resp.json()

            st.success(f"Generated {result['count']} image(s)")

            # Display in grid
            cols = st.columns(min(result["count"], 2))
            for i, img_data in enumerate(result["images"]):
                with cols[i % 2]:
                    img_bytes = base64.b64decode(img_data["base64_image"])
                    st.image(img_bytes, caption=f"Image {i + 1}", use_container_width=True)
                    st.download_button(
                        f"⬇️ Download",
                        data=img_bytes,
                        file_name=f"generated_{i + 1}.png",
                        mime="image/png",
                        key=f"download_{i}",
                    )

            st.caption(f"Model: {result['model']} | Prompt: _{prompt}_")

        except httpx.HTTPError as e:
            st.error(f"Error: {e}")

elif generate_btn and not prompt:
    st.warning("Please enter a prompt.")

# ─── Tips ─────────────────────────────────────────────────────────────────────

with st.expander("💡 Tips for better results"):
    st.markdown("""
    - **Be specific**: "A golden retriever in autumn leaves, shallow depth of field"
    - **Mention style**: "watercolor", "photorealistic", "digital art", "pencil sketch"
    - **Include details**: lighting, camera angle, mood, time of day
    - **Aspect ratios**: 16:9 for landscapes, 9:16 for portraits, 1:1 for icons
    """)
