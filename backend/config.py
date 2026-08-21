"""
Application configuration — loaded from environment variables.

Why a class instead of module-level constants?
- Allows validation at startup (fail fast if GCP_PROJECT_ID is missing)
- Easy to mock in tests
- Single source of truth for all settings
"""

import os
from dotenv import load_dotenv

# Load .env file if present (local dev / Codespace)
load_dotenv()


class Settings:
    """App settings from environment. No defaults for GCP_PROJECT_ID — must be set."""

    GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "")
    GCP_LOCATION: str = os.getenv("GCP_LOCATION", "europe-west2")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "gemini-2.0-flash")
    FIRESTORE_DATABASE: str = os.getenv("FIRESTORE_DATABASE", "(default)")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))

    def validate(self):
        """Raise early if critical config is missing."""
        if not self.GCP_PROJECT_ID:
            raise ValueError(
                "GCP_PROJECT_ID is not set. "
                "Copy .env.example → .env and fill in your GCP project ID."
            )


# Singleton instance used across the app
settings = Settings()
