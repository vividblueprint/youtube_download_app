"""Cross-platform actions for downloaded files."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _open_path(path: Path) -> None:
    path = path.resolve()
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    else:
        subprocess.Popen(["xdg-open", str(path)], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)


def play_file(path: Path) -> None:
    _open_path(path)


def open_folder(path: Path) -> None:
    _open_path(path)
