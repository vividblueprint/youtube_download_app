#!/usr/bin/env sh
set -eu
app_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
binary="$app_dir/dist/youtube-downloader"
if [ ! -x "$binary" ]; then
  echo "Build the app first by running ./build_linux.sh" >&2
  exit 1
fi
mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications" "$HOME/.local/share/icons/hicolor/256x256/apps"
install -m 755 "$binary" "$HOME/.local/bin/youtube-downloader"
install -m 644 "$app_dir/assets/youtube_downloader.png" "$HOME/.local/share/icons/hicolor/256x256/apps/youtube-downloader.png"
cat > "$HOME/.local/share/applications/youtube-downloader.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=YouTube Downloader
Comment=Download selected videos from YouTube playlists
Exec=$HOME/.local/bin/youtube-downloader
TryExec=$HOME/.local/bin/youtube-downloader
Icon=$HOME/.local/share/icons/hicolor/256x256/apps/youtube-downloader.png
Terminal=false
Categories=AudioVideo;Network;
StartupWMClass=YouTubeDownloader
EOF
echo "Installed. Find YouTube Downloader in your applications menu."
