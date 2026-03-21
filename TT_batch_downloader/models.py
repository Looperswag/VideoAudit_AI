"""
Data models for VideoAudit AI TikTok video downloader.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MediaItem:
    """Base class for media items with a string ID."""

    id: str

    def __str__(self) -> str:
        return f"ID: {self.id}"


@dataclass(frozen=True)
class Metadata(MediaItem):
    """TikTok video metadata."""

    title: str
    length: int
    views: int
    author: str
    description: str
    publish_date: str

    def __str__(self) -> str:
        return (
            f"{super().__str__()}\n"
            f"title: {self.title}\n"
            f"length: {self.length}\n"
            f"views: {self.views}\n"
            f"author: {self.author}\n"
            f"publish_date: {self.publish_date}"
        )


@dataclass(frozen=True)
class Video(MediaItem):
    """A downloaded TikTok video file."""

    downloaded_path: str

    def __str__(self) -> str:
        return f"{super().__str__()}\ndownloaded_path: {self.downloaded_path}"
