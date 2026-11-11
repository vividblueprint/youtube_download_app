"""Small, bounded thumbnail fetches that honor the configured proxy."""
from __future__ import annotations

from urllib.request import ProxyHandler, Request, build_opener

MAX_THUMBNAIL_BYTES = 2 * 1024 * 1024

def fetch_thumbnail(url: str, proxy: str = "", fallback_url: str | None = None) -> bytes | None:
    candidates = list(dict.fromkeys(candidate for candidate in (url, fallback_url) if candidate))
    handler = ProxyHandler({"http": proxy, "https": proxy}) if proxy else ProxyHandler()
    opener = build_opener(handler)
    for candidate in candidates:
        request = Request(candidate, headers={"User-Agent": "Mozilla/5.0 YouTubeDownloader/1.0"})
        try:
            with opener.open(request, timeout=12) as response:
                data = response.read(MAX_THUMBNAIL_BYTES + 1)
                if len(data) <= MAX_THUMBNAIL_BYTES:
                    return data
        except Exception:
            continue
    return None
