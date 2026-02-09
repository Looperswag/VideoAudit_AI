"""
Configuration module for VideoAudit AI video processing.

This module handles configuration settings including API credentials,
file paths, and processing parameters.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

# Video file extensions to process
VIDEO_EXTENSIONS: Final = (".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv")

# Maximum video file size in MB
MAX_VIDEO_SIZE_MB: Final[int] = 500

# API timeout in seconds
API_TIMEOUT_SECONDS: Final[int] = 300

# Maximum number of API retries
MAX_RETRIES: Final[int] = 3

# Default gemini model
DEFAULT_GEMINI_MODEL: Final[str] = "gemini-2.5-flash-preview-05-20"


@dataclass
class AppConfig:
    """Application configuration with validation.

    Attributes:
        key_path: Path to Google service account key JSON file.
        project_id: Google Cloud project ID for Vertex AI.
        location: Google Cloud region for Vertex AI.
        video_extensions: Tuple of supported video file extensions.
    """

    key_path: Path
    project_id: str
    location: str
    video_extensions: tuple[str, ...] = VIDEO_EXTENSIONS

    def __post_init__(self) -> None:
        """Validate configuration after initialization.

        Raises:
            ValueError: If configuration values are invalid.
            FileNotFoundError: If key file does not exist.
        """
        # Validate key path exists
        if not self.key_path.exists():
            raise FileNotFoundError(
                f"Google key file not found: {self.key_path}\n"
                f"Please set GOOGLE_KEY_PATH environment variable or "
                f"place key file at: {self.key_path}"
            )

        # Validate project_id
        if not self.project_id or self.project_id.startswith("your_"):
            raise ValueError(
                f"Invalid GEMINI_PROJECT_ID: '{self.project_id}'\n"
                f"Please set GEMINI_PROJECT_ID environment variable "
                f"or update config.py"
            )

        # Validate location
        if not self.location or self.location.startswith("your_"):
            raise ValueError(
                f"Invalid GEMINI_LOCATION: '{self.location}'\n"
                f"Please set GEMINI_LOCATION environment variable "
                f"or update config.py"
            )

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Create configuration from environment variables.

        Environment variables:
            GOOGLE_KEY_PATH: Path to Google service account key (default: ../key.json)
            GEMINI_PROJECT_ID: Google Cloud project ID (required)
            GEMINI_LOCATION: Google Cloud region (default: us-central1)

        Returns:
            AppConfig instance with values from environment.

        Raises:
            ValueError: If required environment variables are missing.
        """
        key_path = Path(
            os.getenv("GOOGLE_KEY_PATH", os.path.join("..", "key.json"))
        )

        project_id = os.getenv(
            "GEMINI_PROJECT_ID", "your_DEFAULT_GEMINI_PROJECT_ID"
        )

        location = os.getenv("GEMINI_LOCATION", "us-central1")

        return cls(
            key_path=key_path,
            project_id=project_id,
            location=location,
        )


# Legacy compatibility - maintain old variable names
# These are deprecated in favor of AppConfig class

# Path to Google API key file
# Use environment variable GOOGLE_KEY_PATH to override
KEY_PATH = os.getenv("GOOGLE_KEY_PATH", "../your_key_file.json")

# Default Gemini project ID
# Use environment variable GEMINI_PROJECT_ID to override
DEFAULT_GEMINI_PROJECT_ID = os.getenv(
    "GEMINI_PROJECT_ID", "your_DEFAULT_GEMINI_PROJECT_ID"
)

# Default Gemini location
# Use environment variable GEMINI_LOCATION to override
DEFAULT_GEMINI_LOCATION = os.getenv("GEMINI_LOCATION", "your_DEFAULT_GEMINI_LOCATION")


def get_config() -> AppConfig:
    """Get validated application configuration.

    Returns:
        AppConfig instance loaded from environment variables.

    Raises:
        ValueError: If configuration is invalid.
        FileNotFoundError: If key file is missing.
    """
    return AppConfig.from_env()
