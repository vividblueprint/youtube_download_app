"""YouTube playlist extraction and download work, separate from the GUI."""
from __future__ import annotations

import re
import threading
from pathlib import Path
from queue import Queue

from .helpers import video_url

class YouTubeService:
    def __init__(self, events: Queue, cancel_event: threading.Event) -> None:
        self.events = events
        self.cancel_event = cancel_event

    def read_playlist(self, link: str, proxy: str = "") -> None:
        try:
            import yt_dlp
            options = {
                "extract_flat": "in_playlist",
                "skip_download": True,
                "quiet": True,
                "no_warnings": True,
                "noplaylist": False,
            }
            if proxy:
                options["proxy"] = proxy
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(link, download=False)
            entries = info.get("entries") or [info]
            items = []
            for entry in entries:
                if not entry:
                    continue
                url = video_url(entry)
                if not url:
                    continue
                thumbnails = entry.get("thumbnails") or []
                thumbnail = entry.get("thumbnail")
                if not thumbnail and thumbnails:
                    thumbnail = next((item.get("url") for item in reversed(thumbnails) if item.get("url")), None)
                video_id = entry.get("id")
                fallback_thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else None
                if not thumbnail:
                    thumbnail = fallback_thumbnail
                items.append({
                    "url": url,
                    "id": video_id,
                    "title": entry.get("title") or entry.get("id") or "Untitled video",
                    "duration": entry.get("duration"),
                    "thumbnail": thumbnail,
                    "thumbnail_fallback": fallback_thumbnail,
                })
            self.events.put(("playlist_loaded", info.get("title") or "YouTube playlist", items, proxy))
        except Exception as exc:
            self.events.put(("playlist_error", str(exc)))

    def download_selected(self, entries: list[dict], folder: Path, mode: str, quality: str, proxy: str = "") -> None:
        import yt_dlp

        failed: list[tuple[str, str]] = []
        completed = 0
        total = len(entries)
        for index, entry in enumerate(entries, start=1):
            if self.cancel_event.is_set():
                break
            self.events.put(("download_item", index, total, entry["title"]))
            if mode == "mp3":
                fmt = "bestaudio/best"
            else:
                height_limit = int(re.search(r"\d+", quality).group()) if quality != "Best available" else None
                height_filter = f"[height<={height_limit}]" if height_limit else ""
                fmt = (
                    f"b[vcodec^=avc1][acodec^=mp4a]{height_filter}/"
                    f"bv[vcodec^=avc1]{height_filter}+ba[acodec^=mp4a]"
                )

            def hook(data: dict, item_index=index) -> None:
                if self.cancel_event.is_set():
                    raise yt_dlp.utils.DownloadError("Download cancelled")
                if data.get("status") == "downloading":
                    total_bytes = data.get("total_bytes") or data.get("total_bytes_estimate")
                    if total_bytes:
                        percent = data.get("downloaded_bytes", 0) / total_bytes * 100
                        self.events.put(("progress", item_index, total, percent, data.get("speed"), data.get("eta")))

            def postprocessor_hook(data: dict, item_index=index) -> None:
                if data.get("status") == "started":
                    self.events.put(("download_status", item_index, total, "Merging video and audio…"))

            options = {
                "format": fmt,
                "merge_output_format": "mp4",
                "outtmpl": str(folder / (
                    "%(title).180B [%(id)s]"
                    f"{entry.get('duplicate_suffix', '')}.%(ext)s"
                )),
                "noplaylist": True,
                "progress_hooks": [hook],
                "postprocessor_hooks": [postprocessor_hook],
                "retries": 3,
                "quiet": True,
                "no_warnings": True,
            }
            if proxy:
                options["proxy"] = proxy
            if mode == "mp3":
                options["postprocessors"] = [{
                    "key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192",
                }]
            try:
                with yt_dlp.YoutubeDL(options) as ydl:
                    result = ydl.download([entry["url"]])
                if result:
                    failed.append((entry["title"], "yt-dlp returned an error"))
                else:
                    completed += 1
            except Exception as exc:
                failed.append((entry["title"], str(exc)))
            self.events.put(("item_complete", index, total, completed, len(failed)))

        self.events.put(("download_finished", completed, total, failed, self.cancel_event.is_set()))
