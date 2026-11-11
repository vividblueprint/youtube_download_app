$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required. Install it from https://docs.astral.sh/uv/ and reopen PowerShell."
}

uv sync
if ($LASTEXITCODE -ne 0) { throw "uv sync failed." }

# Windows executable icons must be ICO files. Build one from the app's PNG logo.
uv run --with pillow python -c "from PIL import Image; Image.open('assets/youtube_downloader.png').convert('RGBA').save('assets/youtube_downloader.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"
if ($LASTEXITCODE -ne 0) { throw "Could not create the Windows icon." }

uv run --with pyinstaller python -m PyInstaller `
    --clean --noconfirm --onefile --windowed `
    --collect-all yt_dlp --collect-all PIL `
    --icon assets/youtube_downloader.ico `
    --add-data "assets/youtube_downloader.png;assets" `
    --name youtube-downloader youtube_downloader.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }

Write-Host "`nWindows app built at: $PSScriptRoot\dist\youtube-downloader.exe"
