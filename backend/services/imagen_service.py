"""
Image generation service using Imagen 3 on Vertex AI.

Imagen 3 is Google's latest text-to-image model, available through Vertex AI.
It supports:
- High-quality photorealistic images
- Various aspect ratios (1:1, 16:9, 9:16, 4:3, 3:4)
- Up to 4 images per request
- Safety filtering

Note: Imagen is a separate model from Gemini — it only generates images,
it doesn't understand them. For image understanding, use gemini_service.
"""

import base64

import vertexai
from vertexai.preview.vision_models import ImageGenerationModel

from backend.config import settings

_initialized = False


def _ensure_init():
    global _initialized
    if not _initialized:
        vertexai.init(project=settings.GCP_PROJECT_ID, location=settings.GCP_LOCATION)
        _initialized = True


async def generate_image(
    prompt: str,
    number_of_images: int = 1,
    aspect_ratio: str = "1:1",
) -> list[dict]:
    """
    Generate images from a text prompt.

    Args:
        prompt: Description of the image to generate
        number_of_images: 1-4 images per request
        aspect_ratio: "1:1", "16:9", "9:16", "4:3", "3:4"

    Returns:
        List of {"base64_image": "...", "mime_type": "image/png"}
    """
    _ensure_init()

    model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-002")

    response = model.generate_images(
        prompt=prompt,
        number_of_images=number_of_images,
        aspect_ratio=aspect_ratio,
        safety_filter_level="block_some",
        person_generation="allow_adult",
    )

    results = []
    for image in response.images:
        image_bytes = image._image_bytes
        results.append({
            "base64_image": base64.b64encode(image_bytes).decode("utf-8"),
            "mime_type": "image/png",
        })

    return results
