"""
Google Gemini AI integration for video content analysis.

This module provides functionality to analyze video content using
Google's Gemini multimodal AI model.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any, Literal

from google import genai
from google.genai import types

from run_video_processing.config import DEFAULT_GEMINI_MODEL, MAX_RETRIES

logger = logging.getLogger(__name__)


# Custom exceptions
class GeminiError(Exception):
    """Base exception for Gemini API errors."""

    pass


class GeminiRateLimitError(GeminiError):
    """Raised when Gemini API rate limit is hit."""

    pass


class GeminiAuthenticationError(GeminiError):
    """Raised when Gemini authentication fails."""

    pass


@dataclass
class LabelResult:
    """Structured result from video labeling.

    Attributes:
        dimension_1: First dimension label (合格/不合格).
        dimension_2: Second dimension label (合格/不合格).
        dimension_3: Third dimension label (合格/不合格).
        dimension_4: Fourth dimension label (合格/不合格).
        raw_response: Raw response text from Gemini.
        final_score: Final score (合格 if all dimensions pass).
    """

    dimension_1: Literal["合格", "不合格"]
    dimension_2: Literal["合格", "不合格"]
    dimension_3: Literal["合格", "不合格"]
    dimension_4: Literal["合格", "不合格"]
    raw_response: str
    final_score: Literal["合格", "不合格"]

    @classmethod
    def parse_from_response(cls, response: str) -> "LabelResult":
        """Parse Gemini response into structured result.

        Args:
            response: Raw response string from Gemini API.

        Returns:
            LabelResult with parsed labels.

        Raises:
            ValueError: If response format is invalid.
        """
        # Clean up response
        cleaned = response.strip()

        # Try to parse labels separated by hyphens
        labels = [label.strip() for label in cleaned.split("-")]

        # Validate we have 4 labels
        if len(labels) != 4:
            logger.warning(f"Expected 4 labels, got {len(labels)}: {labels}")
            # Default to unqualified if format is wrong
            labels = ["不合格", "不合格", "不合格", "不合格"]

        # Validate each label
        for i, label in enumerate(labels):
            if label not in ["合格", "不合格"]:
                logger.warning(f"Invalid label '{label}', defaulting to 不合格")
                labels[i] = "不合格"

        # Calculate final score
        final_score = "合格" if all(label == "合格" for label in labels) else "不合格"

        return cls(
            dimension_1=labels[0],  # type: ignore
            dimension_2=labels[1],  # type: ignore
            dimension_3=labels[2],  # type: ignore
            dimension_4=labels[3],  # type: ignore
            raw_response=response,
            final_score=final_score,  # type: ignore
        )

    def to_filename_safe_string(self) -> str:
        """Convert labels to a filename-safe string.

        Returns:
            Safe string for use in filenames.
        """
        parts = [
            f"环境{self.dimension_1}",
            f"功能{self.dimension_2}",
            f"文案{self.dimension_3}",
            f"品牌{self.dimension_4}",
        ]
        # Sanitize for filename
        safe = "-".join(parts).replace(" ", "_")
        return "".join(
            c if c.isalnum() or c in "-_" else "_" for c in safe
        )


def retry_on_gemini_failure(max_retries: int = MAX_RETRIES, delay: float = 1.0):
    """Decorator to retry Gemini API calls on failure.

    Args:
        max_retries: Maximum number of retry attempts.
        delay: Base delay between retries in seconds (exponential backoff).

    Returns:
        Decorated function with retry logic.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)

                except Exception as e:
                    last_exception = e
                    error_msg = str(e).lower()

                    # Check for rate limit errors
                    if "rate limit" in error_msg or "quota" in error_msg:
                        logger.warning(f"Rate limit hit on attempt {attempt + 1}")
                        if attempt < max_retries - 1:
                            sleep_time = delay * (2**attempt)
                            logger.info(f"Retrying in {sleep_time}s...")
                            time.sleep(sleep_time)
                            continue

                    # Check for auth errors
                    if "auth" in error_msg or "credential" in error_msg:
                        logger.error("Authentication error - not retrying")
                        raise GeminiAuthenticationError(
                            f"Gemini authentication failed: {e}"
                        ) from e

                    # Other errors
                    if attempt < max_retries - 1:
                        sleep_time = delay * (2**attempt)
                        logger.warning(
                            f"Attempt {attempt + 1} failed: {e}, "
                            f"retrying in {sleep_time}s..."
                        )
                        time.sleep(sleep_time)
                    else:
                        logger.error(f"Failed after {max_retries} attempts")

            # All retries failed
            raise GeminiError(f"API call failed: {last_exception}") from last_exception

        return wrapper

    return decorator


# Default prompt for video analysis
# This can be customized for specific use cases
DEFAULT_ANALYSIS_PROMPT = """
请分析此扫地机器人产品视频，并根据以下四个标准进行打标。每个标准输出"合格"或"不合格"。

1. 拍摄环境：是否为清洁场景
2. 功能展示：是否展示产品核心功能
3. 文案合规：是否符合广告法要求
4. 品牌识别：是否能清晰识别品牌

请以以下格式输出（使用 "-" 分隔）：
合格/不合格-合格/不合格-合格/不合格-合格/不合格
"""


def setup_gemini_client(
    project_id: str, location: str, model: str = DEFAULT_GEMINI_MODEL
) -> genai.Client:
    """Set up and return Gemini API client.

    Args:
        project_id: Google Cloud project ID.
        location: Google Cloud region (e.g., us-central1).
        model: Gemini model name to use.

    Returns:
        Configured Gemini API client.

    Raises:
        GeminiAuthenticationError: If client setup fails.
    """
    try:
        client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
        )
        logger.info(f"Gemini client initialized: project={project_id}, location={location}")
        return client

    except Exception as e:
        logger.error(f"Failed to initialize Gemini client: {e}")
        raise GeminiAuthenticationError(f"Client setup failed: {e}") from e


@retry_on_gemini_failure(max_retries=MAX_RETRIES, delay=1.0)
def label_video_with_gemini(
    client: genai.Client,
    video_path: str | Path,
    prompt: str = DEFAULT_ANALYSIS_PROMPT,
    model: str = DEFAULT_GEMINI_MODEL,
) -> LabelResult:
    """Analyze video content using Gemini AI.

    Args:
        client: Configured Gemini API client.
        video_path: Path to the video file to analyze.
        prompt: Analysis prompt to send to Gemini.
        model: Gemini model name to use.

    Returns:
        LabelResult with structured analysis results.

    Raises:
        GeminiError: If analysis fails.
        FileNotFoundError: If video file doesn't exist.
    """
    video_path = Path(video_path)

    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    logger.info(f"Analyzing video: {video_path.name}")

    try:
        # Read video file
        with open(video_path, "rb") as f:
            video_data = f.read()

        # Check file size
        file_size_mb = len(video_data) / (1024 * 1024)
        if file_size_mb > 500:  # Gemini has limits on file size
            logger.warning(
                f"Video file is large ({file_size_mb:.1f}MB), "
                f"may exceed API limits"
            )

        # Create video part
        video_part = types.Part.from_bytes(
            data=video_data,
            mime_type="video/mp4",
        )

        # Create text part with prompt
        text_part = types.Part.from_text(text=prompt)

        # Build content
        contents = [
            types.Content(
                role="user",
                parts=[video_part, text_part],
            )
        ]

        # Generation config
        generate_content_config = types.GenerateContentConfig(
            temperature=0.3,  # Lower temperature for more consistent labeling
            top_p=0.95,
            seed=0,
            max_output_tokens=8192,
            response_modalities=["TEXT"],
        )

        # Call API with streaming
        response_text = ""
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            if chunk.text:
                response_text += chunk.text

        logger.info(f"Gemini response received: {response_text[:100]}...")

        # Parse response into structured result
        result = LabelResult.parse_from_response(response_text)

        return result

    except FileNotFoundError:
        raise
    except GeminiAuthenticationError:
        raise
    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        raise GeminiError(f"Video analysis failed: {e}") from e
