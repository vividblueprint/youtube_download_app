"""Small YouTube metadata and formatting helpers."""
from __future__ import annotations

from urllib.parse import urlparse

def is_youtube_url(value: str) -> bool:
    try:
        host = (urlparse(value.strip()).hostname or "").lower()
        return host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")
    except ValueError:
        return False

def video_url(entry: dict) -> str | None:
    url = entry.get("webpage_url")
    if url and is_youtube_url(url):
        return url
    video_id = entry.get("id")
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    url = entry.get("url")
    return url if url and is_youtube_url(url) else None

def display_duration(seconds) -> str:
    if not isinstance(seconds, (int, float)):
        return ""
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours}:{minutes:02}:{secs:02}" if hours else f"{minutes}:{secs:02}"
