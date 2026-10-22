#!/usr/bin/env sh
set -eu

app_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$app_dir"

command -v dpkg-deb >/dev/null 2>&1 || {
  echo "dpkg-deb is required. Install it with: sudo apt install dpkg-dev" >&2
  exit 1
}

./build_linux.sh

version=$(sed -n 's/^version = "\([^"]*\)"/\1/p' pyproject.toml | head -n 1)
architecture=$(dpkg --print-architecture)
if [ -z "$version" ]; then
  echo "Could not read package version from pyproject.toml" >&2
  exit 1
fi

package_root="$app_dir/build/deb-root"
mkdir -p "$package_root/DEBIAN" \
  "$package_root/opt/youtube-downloader" \
  "$package_root/usr/share/applications" \
  "$package_root/usr/share/icons/hicolor/256x256/apps"

install -m 755 "$app_dir/dist/youtube-downloader" \
  "$package_root/opt/youtube-downloader/youtube-downloader"
install -m 644 "$app_dir/assets/youtube_downloader.png" \
  "$package_root/usr/share/icons/hicolor/256x256/apps/youtube-downloader.png"

cat > "$package_root/usr/share/applications/youtube-downloader.desktop" <<'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=YouTube Downloader
Comment=Download selected videos from YouTube playlists
Exec=/opt/youtube-downloader/youtube-downloader
TryExec=/opt/youtube-downloader/youtube-downloader
Icon=/usr/share/icons/hicolor/256x256/apps/youtube-downloader.png
Terminal=false
Categories=AudioVideo;Network;
StartupWMClass=YouTubeDownloader
EOF

cat > "$package_root/DEBIAN/control" <<EOF
Package: youtube-downloader
Version: $version
Section: video
Priority: optional
Architecture: $architecture
Maintainer: Shamim
Depends: ffmpeg
Description: GUI for downloading selected YouTube videos and playlists
 A Linux desktop application for downloading selected videos and audio
 from YouTube playlists. FFmpeg is used for MP3 conversion and stream merging.
EOF

deb_file="$app_dir/youtube-downloader_${version}_${architecture}.deb"
dpkg-deb --build --root-owner-group "$package_root" "$deb_file"
printf '\nDebian package created: %s\n' "$deb_file"
