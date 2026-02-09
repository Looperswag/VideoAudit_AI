"""
Video utility functions for VideoAudit AI.

This module provides utilities for video duration calculation and time formatting.
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import Any

import cv2

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def video_capture(video_path: str | Path):
    """Context manager for OpenCV VideoCapture to ensure resource cleanup.

    Args:
        video_path: Path to the video file.

    Yields:
        VideoCapture object if video can be opened.

    Raises:
        RuntimeError: If video file cannot be opened.
    """
    cap = cv2.VideoCapture(str(video_path))
    try:
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")
        yield cap
    finally:
        cap.release()


def format_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS.mmm timestamp.

    Args:
        seconds: Time in seconds.

    Returns:
        Formatted timestamp string.
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def format_duration_human(seconds: float) -> str:
    """Format seconds as human-readable duration.

    Args:
        seconds: Time in seconds.

    Returns:
        Human-readable duration string (e.g., "5 min, 30 s").
    """
    minutes, secs = divmod(int(seconds), 60)
    if minutes > 0:
        return f"{minutes} min, {secs} s"
    return f"{secs} s"


def get_video_duration(video_path: str | Path) -> float:
    """Get video duration in seconds.

    Args:
        video_path: Path to the video file.

    Returns:
        Video duration in seconds, or 0.0 if unable to determine.
    """
    try:
        with video_capture(video_path) as cap:
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            if fps <= 0:
                logger.warning(f"Invalid FPS for {video_path}: {fps}")
                return 0.0

            duration = frame_count / fps
            return duration

    except Exception as e:
        logger.error(f"Failed to get duration for {video_path}: {e}")
        return 0.0


def get_video_info(video_path: str | Path) -> dict[str, Any]:
    """Get comprehensive video information.

    Args:
        video_path: Path to the video file.

    Returns:
        Dictionary containing video metadata including fps, frame count,
        duration, width, and height.
    """
    try:
        with video_capture(video_path) as cap:
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            duration = 0.0
            if fps > 0:
                duration = frame_count / fps

            return {
                "fps": fps,
                "frame_count": frame_count,
                "width": width,
                "height": height,
                "duration": duration,
                "resolution": f"{width}x{height}",
            }

    except Exception as e:
        logger.error(f"Failed to get video info for {video_path}: {e}")
        return {
            "fps": 0,
            "frame_count": 0,
            "width": 0,
            "height": 0,
            "duration": 0.0,
            "resolution": "0x0",
        }
