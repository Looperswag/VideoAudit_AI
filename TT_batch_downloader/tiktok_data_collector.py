"""
TikTok video data collector module.

This module provides functionality to collect video data and metadata
from TikTok URLs using the yt-dlp library.
"""

from __future__ import annotations

import logging
import os
import time
from functools import wraps
from pathlib import Path
from typing import Callable, Literal

import yt_dlp

from TT_batch_downloader.models import Video, Metadata

# Configure module logger
logger = logging.getLogger(__name__)


# Custom exceptions for better error handling
class TikTokDownloadError(Exception):
    """Base exception for TikTok download errors."""

    pass


class VideoNotFoundError(TikTokDownloadError):
    """Raised when video is not found or inaccessible."""

    pass


class RateLimitError(TikTokDownloadError):
    """Raised when rate limit is hit."""

    pass


def rate_limit(delay: float) -> Callable:
    """Decorator to rate limit function calls.

    Args:
        delay: Minimum delay in seconds between calls.

    Returns:
        Decorated function with rate limiting.
    """

    def decorator(func: Callable) -> Callable:
        last_called = [0.0]

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            elapsed = time.time() - last_called[0]
            if elapsed < delay:
                sleep_time = delay - elapsed
                logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)
            result = func(*args, **kwargs)
            last_called[0] = time.time()
            return result

        return wrapper

    return decorator


class TikTokVideoCollector:
    """Collects TikTok video data and downloads videos.

    This class handles downloading videos from TikTok URLs and extracting
    associated metadata using yt-dlp.
    """

    DEFAULT_DOWNLOAD_PATH = Path("videos")

    def __init__(
        self,
        cookies_path: str | None = None,
        use_browser_cookies: bool = False,
        rate_limit_delay: float = 1.0,
    ) -> None:
        """Initialize the TikTok video collector.

        Args:
            cookies_path: Path to cookies file for authenticated requests.
            use_browser_cookies: Whether to use browser cookies.
            rate_limit_delay: Delay in seconds between downloads to avoid rate limiting.
        """
        self.cookies_path = cookies_path
        self.use_browser_cookies = use_browser_cookies
        self.rate_limit_delay = rate_limit_delay

    @rate_limit(delay=1.0)
    def collect(
        self,
        url: str,
        download_path: str | Path | None = None,
        progress_callback: Callable[[str, int], None] | None = None,
    ) -> tuple[Video, Metadata] | None:
        """Collect video data from TikTok URL.

        Args:
            url: TikTok video URL.
            download_path: Directory to save downloaded videos.
            progress_callback: Optional callback for progress updates (url, percent).

        Returns:
            Tuple of Video and Metadata objects if successful, None otherwise.

        Raises:
            VideoNotFoundError: If video cannot be found or accessed.
            RateLimitError: If rate limit is hit.
            TikTokDownloadError: For other download errors.
        """
        logger.info(f"Starting collection for video URL: {url}")

        if progress_callback:
            progress_callback(url, 0)

        # Set download path
        if download_path is None:
            download_path = self.DEFAULT_DOWNLOAD_PATH

        download_path = Path(download_path)
        download_path.mkdir(parents=True, exist_ok=True)

        # Configure yt-dlp options
        ydl_opts = self._get_ydl_options(download_path)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if progress_callback:
                    progress_callback(url, 25)

                # Extract video info and download
                info = ydl.extract_info(url, download=True)

                if info is None:
                    raise VideoNotFoundError(f"Video not found: {url}")

                if progress_callback:
                    progress_callback(url, 75)

                # Build video path
                video_filename = f"{info['id']}.mp4"
                video_path = download_path / video_filename

                # Verify file exists
                if not video_path.exists():
                    # Try alternative extension
                    video_path = download_path / f"{info['id']}.webm"
                    if not video_path.exists():
                        raise TikTokDownloadError(
                            f"Video file not found after download: {info['id']}"
                        )

                # Create Video and Metadata objects
                video_obj = Video(
                    id=info["id"],
                    downloaded_path=str(video_path),
                )

                metadata = Metadata(
                    id=info["id"],
                    title=info.get("title", "N/A"),
                    length=info.get("duration", 0),
                    views=info.get("view_count", 0),
                    author=info.get("uploader", "N/A"),
                    description=info.get("description", ""),
                    publish_date=info.get("upload_date", "N/A"),
                )

                logger.info(f"Collection successful for video ID: {info['id']}")

                if progress_callback:
                    progress_callback(url, 100)

                return video_obj, metadata

        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e).lower()
            if "rate limit" in error_msg or "too many requests" in error_msg:
                logger.error(f"Rate limit hit for {url}: {e}")
                raise RateLimitError(f"Rate limit exceeded: {e}") from e
            logger.error(f"Download error for {url}: {e}")
            raise VideoNotFoundError(f"Failed to download video: {e}") from e

        except Exception as e:
            logger.error(f"Unexpected error during collection: {e}")
            raise TikTokDownloadError(f"Collection failed: {e}") from e

    def _get_ydl_options(self, download_path: Path) -> dict[str, Any]:
        """Build yt-dlp options dictionary.

        Args:
            download_path: Path where videos should be downloaded.

        Returns:
            Dictionary of yt-dlp options.
        """
        opts: dict[str, Any] = {
            "format": "bestvideo+bestaudio/best",
            "outtmpl": str(download_path / "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
        }

        # Add cookies if configured
        if self.cookies_path and Path(self.cookies_path).exists():
            opts["cookies"] = self.cookies_path
            logger.debug(f"Using cookies from: {self.cookies_path}")

        elif self.use_browser_cookies:
            opts["cookiesfrombrowser"] = ("chrome",)
            logger.debug("Using Chrome browser cookies")

        return opts


# Legacy compatibility - keep old class name
class TikTokDataCollector:
    """Legacy base class for backward compatibility.

    Deprecated: Use TikTokVideoCollector directly.
    """

    def __init__(self) -> None:
        logger.warning(
            "TikTokDataCollector is deprecated. Use TikTokVideoCollector instead."
        )
        pass

    def get_video_data(self, url: str) -> dict[str, Any] | None:
        """Fetch video data using yt_dlp without downloading.

        Args:
            url: The TikTok video URL.

        Returns:
            Dictionary containing video information or None on failure.
        """
        try:
            ydl_opts = {
                "format": "bestvideo+bestaudio/best",
                "quiet": True,
                "no_warnings": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                video_info = ydl.extract_info(url, download=False)
                return video_info

        except Exception as e:
            logger.error(f"Error fetching video data: {e}")
            return None
