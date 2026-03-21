"""
Configuration module for VideoAudit AI video processing.

Loads settings from environment variables with mandatory validation —
no placeholder defaults are accepted at runtime.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

# ── Constants ─────────────────────────────────────────────────────────────────

VIDEO_EXTENSIONS: Final[tuple[str, ...]] = (".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv")
MAX_VIDEO_SIZE_MB: Final[int] = 500
API_TIMEOUT_SECONDS: Final[int] = 300
MAX_RETRIES: Final[int] = 3
DEFAULT_GEMINI_MODEL: Final[str] = "gemini-2.5-flash-preview-05-20"

# Sentinel — used to detect missing env vars (distinct from any valid value)
_UNSET: Final = object()


# ── Dataclass config ───────────────────────────────────────────────────────────

@dataclass
class AppConfig:
    """Validated application configuration.

    Attributes:
        key_path:     Path to Google service-account key JSON.
        project_id:   Google Cloud project ID for Vertex AI.
        location:     Google Cloud region (e.g. us-central1).
        video_extensions: Recognised video file extensions.
    """

    key_path: Path
    project_id: str
    location: str
    video_extensions: tuple[str, ...] = VIDEO_EXTENSIONS

    def __post_init__(self) -> None:
        # Key file must exist on disk
        if not self.key_path.exists():
            raise FileNotFoundError(
                f"[CONFIG] Google key file not found: {self.key_path}\n"
                "  → Set GOOGLE_KEY_PATH env var or place the JSON key alongside config.py"
            )

        # Guard against accidental placeholder values
        if not self.project_id or self.project_id.startswith("your_"):
            raise ValueError(
                f"[CONFIG] Invalid GEMINI_PROJECT_ID: '{self.project_id}'\n"
                "  → Set GEMINI_PROJECT_ID env var to your actual GCP project ID"
            )

        if not self.location or self.location.startswith("your_"):
            raise ValueError(
                f"[CONFIG] Invalid GEMINI_LOCATION: '{self.location}'\n"
                "  → Set GEMINI_LOCATION env var (e.g. us-central1)"
            )

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Build a validated config from environment variables."""
        key_path = Path(os.getenv("GOOGLE_KEY_PATH", "key.json")).expanduser()

        project_id = os.getenv("GEMINI_PROJECT_ID", "")
        location = os.getenv("GEMINI_LOCATION", "")

        return cls(key_path=key_path, project_id=project_id, location=location)


# ── Legacy module-level helpers (deprecated) ───────────────────────────────────

KEY_PATH: Final = os.getenv("GOOGLE_KEY_PATH", "key.json")
"""Deprecated — use AppConfig.from_env() instead."""


def get_config() -> AppConfig:
    """Convenience wrapper: return a fully-validated AppConfig instance."""
    return AppConfig.from_env()
