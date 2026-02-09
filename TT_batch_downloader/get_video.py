"""
TikTok video batch downloader module.

This module provides the GetTiktokVideo class for downloading multiple
TikTok videos with progress tracking and duplicate detection.
"""

from __future__ import annotations

import csv
import logging
import os
import time
from pathlib import Path
from typing import Any

import pandas as pd

from TT_batch_downloader.tiktok_data_collector import TikTokVideoCollector, TikTokDownloadError
from TT_batch_downloader.models import Video, Metadata

logger = logging.getLogger(__name__)


class GetTiktokVideo:
    """Batch downloader for TikTok videos with CSV tracking.

    This class handles downloading multiple TikTok videos from a CSV file
    and tracking progress in CSV files within subfolders.

    Deprecated: Consider using TikTokBatchDownloader from main.py instead.
    """

    def __init__(self, url_csv_path: str | Path, video_download_path: str | Path) -> None:
        """Initialize the TikTok video downloader.

        Args:
            url_csv_path: Path to CSV file containing video URLs.
            video_download_path: Directory to save downloaded videos.
        """
        self.url_list = self._get_url_list(url_csv_path)
        self.video_download_path = Path(video_download_path)
        self.collector = TikTokVideoCollector()

    def _get_url_list(self, url_csv_path: str | Path) -> list[str]:
        """Extract URLs from CSV file with robust encoding detection.

        Args:
            url_csv_path: Path to the CSV file.

        Returns:
            List of valid TikTok URLs.
        """
        encodings = ["utf-8", "iso-8859-1", "gbk", "gb2312", "latin1"]

        for encoding in encodings:
            try:
                df = pd.read_csv(
                    str(url_csv_path),
                    encoding=encoding,
                    on_bad_lines="skip",
                )

                # Find URL column
                url_column = self._find_url_column(df)
                if not url_column:
                    continue

                urls = df[url_column].dropna().tolist()

                # Validate URLs
                valid_urls = [
                    url
                    for url in urls
                    if isinstance(url, str) and url.startswith(("http://", "https://"))
                ]

                if valid_urls:
                    logger.info(
                        f"Successfully read {len(valid_urls)} URLs "
                        f"using encoding: {encoding}"
                    )
                    return valid_urls

            except Exception as e:
                logger.debug(f"Failed to read CSV with encoding {encoding}: {e}")
                continue

        # Fallback: regex extraction
        logger.warning("CSV parsing failed, attempting regex extraction")
        return self._extract_urls_regex(url_csv_path)

    def _find_url_column(self, df: pd.DataFrame) -> str | None:
        """Find the column containing URLs.

        Args:
            df: DataFrame to search.

        Returns:
            Column name containing URLs or None.
        """
        if "url" in df.columns:
            return "url"

        # Search for columns with url/link in name
        for col in df.columns:
            if any(keyword in col.lower() for keyword in ["url", "link"]):
                logger.info(f"Using URL column: {col}")
                return col

        # Check first column
        if not df.empty:
            first_col = df.columns[0]
            logger.warning(f"No URL column found, using first column: {first_col}")
            return first_col

        return None

    def _extract_urls_regex(self, file_path: str | Path) -> list[str]:
        """Extract URLs from file using regex.

        Args:
            file_path: Path to the file.

        Returns:
            List of URLs found.
        """
        import re

        for encoding in ["utf-8", "iso-8859-1", "latin1"]:
            try:
                with open(file_path, "r", encoding=encoding, errors="replace") as f:
                    content = f.read()

                urls = re.findall(r"https?://[^\s,\"';]+", content)

                if urls:
                    logger.info(f"Extracted {len(urls)} URLs using regex")
                    return urls

            except Exception as e:
                logger.debug(f"Regex extraction with encoding {encoding} failed: {e}")
                continue

        logger.error("Failed to extract URLs using all methods")
        return []

    def retry_collect(
        self,
        collector: TikTokVideoCollector,
        url: str,
        download_path: Path,
        max_retries: int = 3,
        delay: int = 5,
    ) -> tuple[Video | None, Metadata | None]:
        """Collect video with retry logic.

        Args:
            collector: Video collector instance.
            url: TikTok video URL.
            download_path: Directory to save the video.
            max_retries: Maximum retry attempts.
            delay: Delay between retries in seconds.

        Returns:
            Tuple of Video and Metadata objects, or (None, None) if all retries fail.
        """
        for attempt in range(max_retries):
            try:
                result = collector.collect(str(url), str(download_path))
                if result:
                    return result

            except TikTokDownloadError as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")

                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    logger.error(f"Failed after {max_retries} attempts: {url}")

        return None, None

    def download_video(self) -> None:
        """Download all videos from the URL list.

        Videos are organized into subfolders with progress tracking in CSV files.
        """
        max_videos_per_folder = 100

        for index, url in enumerate(self.url_list):
            logger.info(f"Starting download for: {url}")

            # Calculate subfolder
            subfolder_index = (index // max_videos_per_folder) + 1
            subfolder_name = f"video{subfolder_index}"
            subfolder_path = self.video_download_path / subfolder_name
            subfolder_path.mkdir(parents=True, exist_ok=True)

            # Setup CSV tracking
            csv_path = subfolder_path / "id2url.csv"
            existing_urls = self._load_existing_urls(csv_path)

            # Check if already processed
            if url in existing_urls:
                logger.info(f"URL already processed, skipping: {url}")
                continue

            # Download video
            video, metadata = self.retry_collect(
                self.collector, url, subfolder_path
            )

            if video is None or metadata is None:
                logger.warning(f"Failed to download: {url}")
                continue

            # Print metadata
            print(metadata)
            print(f"video download path: {video.downloaded_path}")

            # Record download
            self._record_download(csv_path, url, str(video.downloaded_path))

    def _load_existing_urls(self, csv_path: Path) -> set[str]:
        """Load existing URLs from CSV tracking file.

        Args:
            csv_path: Path to the CSV file.

        Returns:
            Set of URLs already processed.
        """
        if not csv_path.exists():
            # Create CSV with headers
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["url", "Video Path"])
            return set()

        existing_urls = set()
        try:
            with open(csv_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("url"):
                        existing_urls.add(row["url"])
        except Exception as e:
            logger.warning(f"Error loading existing URLs: {e}")

        return existing_urls

    def _record_download(self, csv_path: Path, url: str, video_path: str) -> None:
        """Record a successful download to the CSV file.

        Args:
            csv_path: Path to the CSV file.
            url: The downloaded video URL.
            video_path: Path where the video was saved.
        """
        try:
            with open(csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([url, video_path])
            logger.debug(f"Recorded download: {url}")
        except Exception as e:
            logger.error(f"Error recording download: {e}")
