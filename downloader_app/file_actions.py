"""Cross-platform actions for downloaded files."""
from __future__ import annotations

import subprocess
from pathlib import Path

def play_file(path: Path) -> None:
    subprocess.Popen(
        ["xdg-open", str(path)], stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

def open_folder(path: Path) -> None:
    subprocess.Popen(
        ["xdg-open", str(path)], stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
