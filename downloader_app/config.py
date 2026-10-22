"""Application defaults, theme colors, and persisted user preferences."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP_NAME = "YouTube Downloader"
DEFAULT_FOLDER = Path.home() / "Videos"
# DEFAULT_FOLDER = Path.home() / "Desktop" / "videos"
DEFAULT_PROXY = "http://127.0.0.1:7890/"
URL_PLACEHOLDER = "https://www.youtube.com/playlist?list=PLAYLIST_ID"
BG = "#101318"
PANEL = "#191e26"
PANEL_LIGHT = "#222a35"
TEXT = "#f4f6f8"
MUTED = "#9aa6b5"
ACCENT = "#ff4d5e"
GREEN = "#40d7a2"

def resource_path(relative_path: str) -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return bundle_root / relative_path

def settings_file_path() -> Path:
    config_root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_root / "youtube-downloader" / "settings.json"

def load_settings(path: Path) -> dict:
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
        return settings if isinstance(settings, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}

def save_settings(path: Path, settings: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    temporary_path.replace(path)
    try:
        path.chmod(0o600)
    except OSError:
        pass
