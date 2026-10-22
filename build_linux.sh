#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
uv run --with pyinstaller --with pillow python -m PyInstaller \
  --clean --noconfirm --onefile --windowed --collect-all yt_dlp --collect-all PIL \
  --icon assets/youtube_downloader.png --add-data "assets/youtube_downloader.png:assets" \
  --name youtube-downloader youtube_downloader.py
printf '\nLinux app built at: %s/dist/youtube-downloader\n' "$PWD"
