#!/usr/bin/env sh
set -eu

rm -f "$HOME/.local/bin/youtube-downloader"
rm -f "$HOME/.local/share/applications/youtube-downloader.desktop"
rm -f "$HOME/.local/share/icons/hicolor/256x256/apps/youtube-downloader.png"

printf "YouTube Downloader was removed from this user account.\n"
