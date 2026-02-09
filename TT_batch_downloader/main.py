"""
VideoAudit AI - TikTok Batch Video Downloader

Main entry point for downloading TikTok videos from URL lists.
Supports CSV, TXT, and ZIP files as input sources.
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from TT_batch_downloader.tiktok_data_collector import TikTokVideoCollector, TikTokDownloadError
from TT_batch_downloader.models import Video, Metadata

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("tiktok_download.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class FileType:
    """File type constants."""

    ZIP = "zip"
    TEXT = "text"
    UNKNOWN = "unknown"


class URLExtractor:
    """Extract URLs from various file formats with encoding detection."""

    ENCODINGS = ["utf-8", "iso-8859-1", "gbk", "gb2312", "latin1"]
    SEPARATORS = [",", ";", "\t"]

    def extract_from_file(self, file_path: str | Path) -> list[str]:
        """Extract URLs from CSV, TXT, or ZIP files.

        Args:
            file_path: Path to the file to extract URLs from.

        Returns:
            List of valid URLs found in the file.

        Raises:
            ValueError: If no URLs can be extracted.
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        file_type = self._check_file_type(file_path)
        logger.info(f"Detected file type: {file_type}")

        if file_type == FileType.ZIP:
            return self._extract_from_zip(file_path)

        return self._extract_from_text_file(file_path)

    def _check_file_type(self, file_path: Path) -> str:
        """Detect file type by reading magic bytes.

        Args:
            file_path: Path to the file.

        Returns:
            File type constant.
        """
        try:
            with open(file_path, "rb") as f:
                header = f.read(4)

            # Check for ZIP file magic number (PK)
            if header[:2] == b"PK":
                return FileType.ZIP

            # Try to read as text to detect CSV/text
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if any(sep in first_line for sep in [",", ";", "\t"]):
                        return FileType.TEXT
                    return FileType.TEXT
            except UnicodeDecodeError:
                pass

        except Exception as e:
            logger.error(f"Error checking file type: {e}")

        return FileType.UNKNOWN

    def _extract_from_zip(self, zip_path: Path) -> list[str]:
        """Extract URLs from a ZIP archive.

        Args:
            zip_path: Path to the ZIP file.

        Returns:
            List of extracted URLs.
        """
        extract_folder = zip_path.parent / f"{zip_path.stem}_extracted"
        extract_folder.mkdir(exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_folder)

            # Look for CSV files first
            for csv_file in extract_folder.rglob("*.csv"):
                logger.info(f"Found CSV in ZIP: {csv_file}")
                urls = self._extract_from_text_file(csv_file)
                if urls:
                    return urls

            # If no CSV found, look for TXT files
            for txt_file in extract_folder.rglob("*.txt"):
                logger.info(f"Found TXT in ZIP: {txt_file}")
                urls = self._extract_from_text_file(txt_file)
                if urls:
                    return urls

            raise ValueError("No CSV or TXT files found in ZIP archive")

        except Exception as e:
            logger.error(f"Error extracting from ZIP: {e}")
            raise

    def _extract_from_text_file(self, file_path: Path) -> list[str]:
        """Extract URLs from a CSV or text file.

        Args:
            file_path: Path to the text/CSV file.

        Returns:
            List of extracted URLs.
        """
        # Try parsing as CSV with different encodings and separators
        for encoding in self.ENCODINGS:
            for separator in self.SEPARATORS:
                try:
                    urls = self._try_read_csv(file_path, encoding, separator)
                    if urls:
                        logger.info(
                            f"Successfully read {len(urls)} URLs using "
                            f"encoding={encoding}, separator='{separator}'"
                        )
                        return urls
                except Exception:
                    continue

        # Fallback: extract URLs using regex
        return self._extract_urls_regex(file_path)

    def _try_read_csv(
        self, file_path: Path, encoding: str, separator: str
    ) -> list[str]:
        """Try reading file as CSV with specific parameters.

        Args:
            file_path: Path to the CSV file.
            encoding: Text encoding to use.
            separator: Field separator.

        Returns:
            List of URLs extracted from the CSV.

        Raises:
            Exception: If CSV parsing fails.
        """
        df = pd.read_csv(file_path, encoding=encoding, sep=separator, on_bad_lines="skip")

        # Find URL column
        url_column = self._find_url_column(df)
        if not url_column:
            return []

        # Extract and validate URLs
        urls = df[url_column].dropna().tolist()
        return [url for url in urls if isinstance(url, str) and url.startswith("http")]

    def _find_url_column(self, df: pd.DataFrame) -> str | None:
        """Find the column containing URLs.

        Args:
            df: DataFrame to search.

        Returns:
            Column name containing URLs or None.
        """
        # Check for 'url' column
        if "url" in df.columns:
            return "url"

        # Search for columns with url/link in name
        for col in df.columns:
            if any(keyword in col.lower() for keyword in ["url", "link"]):
                return col

        # Check first column's values
        if not df.empty:
            first_col = df.columns[0]
            sample_values = df[first_col].dropna().head(5).tolist()
            if any(
                isinstance(v, str) and v.startswith("http") for v in sample_values
            ):
                return first_col

        return None

    def _extract_urls_regex(self, file_path: Path) -> list[str]:
        """Extract URLs from file using regex.

        Args:
            file_path: Path to the file.

        Returns:
            List of URLs found.
        """
        for encoding in self.ENCODINGS:
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


class DownloadTracker:
    """Track download progress and avoid duplicate downloads."""

    CSV_FILENAME = "id2url.csv"

    def __init__(self, csv_path: Path) -> None:
        """Initialize tracker with CSV file path.

        Args:
            csv_path: Path to the tracking CSV file.
        """
        self.csv_path = csv_path
        self.existing_urls: set[str] = set()
        self._load_existing_urls()

    def _load_existing_urls(self) -> None:
        """Load existing URLs from CSV file."""
        if self.csv_path.exists():
            try:
                with open(self.csv_path, "r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    self.existing_urls = {
                        row["url"] for row in reader if row.get("url")
                    }
                logger.info(f"Loaded {len(self.existing_urls)} existing URLs")
            except Exception as e:
                logger.warning(f"Error loading existing URLs: {e}")

        self._ensure_csv_exists()

    def _ensure_csv_exists(self) -> None:
        """Create CSV file with headers if it doesn't exist."""
        if not self.csv_path.exists():
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["url", "Video Path"])

    def is_processed(self, url: str) -> bool:
        """Check if URL has already been processed.

        Args:
            url: URL to check.

        Returns:
            True if URL was already processed.
        """
        return url in self.existing_urls

    def record_download(self, url: str, video_path: str) -> None:
        """Record a successful download to the CSV.

        Args:
            url: The downloaded video URL.
            video_path: Path where video was saved.
        """
        try:
            with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([url, video_path])
            self.existing_urls.add(url)
            logger.debug(f"Recorded download: {url}")
        except Exception as e:
            logger.error(f"Error recording download: {e}")


@dataclass
class DownloadConfig:
    """Configuration for batch download.

    Attributes:
        input_path: Path to input file with URLs.
        output_path: Directory to save downloaded videos.
        max_videos_per_folder: Maximum videos per subfolder.
        max_retries: Maximum download retry attempts.
        retry_delay: Delay between retries in seconds.
    """

    input_path: Path
    output_path: Path
    max_videos_per_folder: int = 100
    max_retries: int = 3
    retry_delay: int = 5


class TikTokBatchDownloader:
    """Batch downloader for TikTok videos with progress tracking."""

    def __init__(self, config: DownloadConfig) -> None:
        """Initialize batch downloader.

        Args:
            config: Download configuration.
        """
        self.config = config
        self.collector = TikTokVideoCollector()
        self.url_extractor = URLExtractor()

    def download_all(self) -> dict[str, Any]:
        """Download all videos from the configured URL list.

        Returns:
            Summary dictionary with download statistics.
        """
        logger.info("Starting batch download...")

        # Extract URLs
        try:
            url_list = self.url_extractor.extract_from_file(self.config.input_path)
        except Exception as e:
            logger.error(f"Failed to extract URLs: {e}")
            return {"success": False, "error": str(e), "downloaded": 0, "failed": 0}

        if not url_list:
            logger.error("No valid URLs found")
            return {"success": False, "error": "No URLs found", "downloaded": 0, "failed": 0}

        logger.info(f"Found {len(url_list)} URLs to download")

        # Create output directory
        self.config.output_path.mkdir(parents=True, exist_ok=True)

        # Download videos
        downloaded_count = 0
        failed_count = 0

        for index, url in enumerate(url_list):
            subfolder_index = (index // self.config.max_videos_per_folder) + 1
            subfolder_path = (
                self.config.output_path / f"video{subfolder_index}"
            )
            subfolder_path.mkdir(exist_ok=True)

            tracker = DownloadTracker(subfolder_path / DownloadTracker.CSV_FILENAME)

            if tracker.is_processed(url):
                logger.info(f"Skipping already processed: {url}")
                continue

            result = self._download_single(url, subfolder_path)
            if result["success"]:
                tracker.record_download(url, result["video_path"])
                downloaded_count += 1
            else:
                failed_count += 1

        summary = {
            "success": True,
            "downloaded": downloaded_count,
            "failed": failed_count,
            "total": len(url_list),
        }

        logger.info(f"Batch download complete: {downloaded_count} downloaded, {failed_count} failed")
        return summary

    def _download_single(self, url: str, output_path: Path) -> dict[str, Any]:
        """Download a single video with retry logic.

        Args:
            url: TikTok video URL.
            output_path: Directory to save the video.

        Returns:
            Result dictionary with success status.
        """
        for attempt in range(self.config.max_retries):
            try:
                logger.info(f"Downloading (attempt {attempt + 1}): {url}")

                video, metadata = self.collector.collect(url, output_path)

                if video:
                    logger.info(f"Success: {metadata.id}")
                    print(metadata)
                    print(f"video download path: {video.downloaded_path}")

                    return {
                        "success": True,
                        "video_path": video.downloaded_path,
                        "metadata": metadata,
                    }

            except TikTokDownloadError as e:
                logger.warning(f"Download attempt {attempt + 1} failed: {e}")

                if attempt < self.config.max_retries - 1:
                    import time

                    logger.info(f"Retrying in {self.config.retry_delay} seconds...")
                    time.sleep(self.config.retry_delay)
                else:
                    logger.error(f"Failed after {self.config.max_retries} attempts: {url}")

        return {"success": False, "error": "Max retries exceeded"}


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="VideoAudit AI - Batch TikTok Video Downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download from CSV file
  python -m TT_batch_downloader.main -i urls.csv -o downloaded_videos

  # Download from ZIP file
  python -m TT_batch_downloader.main -i videos.zip -o downloaded_videos

  # Download with custom folder size
  python -m TT_batch_downloader.main -i urls.csv -o downloaded_videos --max-videos 50
        """,
    )

    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        required=True,
        help="Path to input file (CSV, TXT, or ZIP) containing video URLs",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("downloaded_videos"),
        help="Output directory for downloaded videos (default: downloaded_videos)",
    )

    parser.add_argument(
        "--max-videos",
        type=int,
        default=100,
        help="Maximum videos per subfolder (default: 100)",
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum download retry attempts (default: 3)",
    )

    parser.add_argument(
        "--retry-delay",
        type=int,
        default=5,
        help="Delay between retries in seconds (default: 5)",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point for the TikTok batch downloader."""
    args = parse_arguments()

    config = DownloadConfig(
        input_path=args.input,
        output_path=args.output,
        max_videos_per_folder=args.max_videos,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
    )

    downloader = TikTokBatchDownloader(config)
    summary = downloader.download_all()

    if summary["success"]:
        logger.info(f"Download complete: {summary['downloaded']}/{summary['total']} videos")
    else:
        logger.error(f"Download failed: {summary.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()
