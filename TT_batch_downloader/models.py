"""
Data models for VideoAudit AI TikTok video downloader.

This module defines data structures for representing video metadata,
media items, and related content collected from TikTok.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class MediaItem:
    """Base class for media items with an ID.

    Attributes:
        id: Unique identifier for the media item.
    """

    id: str

    def __str__(self) -> str:
        """Return string representation of the media item."""
        return f"ID: {self.id}"


@dataclass(frozen=True)
class Metadata(MediaItem):
    """Metadata for a TikTok video.

    Attributes:
        title: Video title.
        length: Video duration in seconds.
        views: Number of views.
        author: Video author/uploader.
        description: Video description text.
        publish_date: When the video was published.
    """

    title: str
    length: int
    views: int
    author: str
    description: str
    publish_date: str

    def __str__(self) -> str:
        """Return formatted metadata string."""
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
    """Represents a downloaded TikTok video.

    Attributes:
        downloaded_path: Filesystem path to the downloaded video.
    """

    downloaded_path: str

    def __str__(self) -> str:
        """Return formatted video info string."""
        return f"{super().__str__()}\ndownloaded_path: {self.downloaded_path}"


# TODO: Remove unused classes (Audio, Comment, Text) or document their usage
# These are defined but currently not used in the downloader module.

@dataclass(frozen=True)
class Audio(MediaItem):
    """Represents extracted audio from a video.

    Attributes:
        audio_path: Filesystem path to the audio file.
    """

    audio_path: str

    def __str__(self) -> str:
        """Return formatted audio info string."""
        return f"{super().__str__()}\naudio_path: {self.audio_path}"


@dataclass(frozen=True)
class Comment:
    """Represents a comment on a video.

    Attributes:
        video_id: ID of the video being commented on.
        author: Username of the commenter.
        text: Comment text content.
        published_at: When the comment was published.
    """

    video_id: str
    author: str
    text: str
    published_at: str

    def __str__(self) -> str:
        """Return formatted comment string."""
        return (
            f"ID: {self.video_id}\n"
            f"Author: {self.author}\n"
            f"Comment: {self.text}\n"
            f"Published at: {self.published_at}\n"
            + "-" * 80
        )


@dataclass
class Text:
    """Aggregates all text content related to a video.

    Attributes:
        video_id: ID of the video.
        comments: List of comments on the video.
        hashtags: List of hashtags associated with the video.
        captions: Caption/subtitle text if available.
    """

    video_id: str
    comments: list[Comment]
    hashtags: list[str]
    captions: str | None = None

    def add_comment(self, comment: Comment) -> None:
        """Add a comment to the comments list.

        Args:
            comment: Comment object to add.
        """
        self.comments.append(comment)

    def add_hashtags(self, hashtags: list[str]) -> None:
        """Add hashtags to the hashtags list.

        Args:
            hashtags: List of hashtag strings to add.
        """
        self.hashtags.extend(hashtags)

    def add_captions(self, captions: str) -> None:
        """Set the captions text.

        Args:
            captions: Caption/subtitle text.
        """
        self.captions = captions

    def __str__(self) -> str:
        """Return formatted text content string."""
        hashtags_str = ", ".join(self.hashtags)
        comments_str = "\n".join(str(comment) for comment in self.comments)
        captions_str = self.captions if self.captions else "No captions available"
        return (
            f"ID: {self.video_id}\n"
            f"Hashtags: {hashtags_str}\n"
            f"Comments:\n{comments_str}\n"
            f"Captions:\n{captions_str}"
        )
