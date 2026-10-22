from __future__ import annotations

import importlib.util
import os
import re
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageOps, ImageTk

from downloader_app.config import (
    ACCENT, APP_NAME, BG, DEFAULT_FOLDER, DEFAULT_PROXY, MUTED, PANEL,
    PANEL_LIGHT, TEXT, URL_PLACEHOLDER, load_settings, resource_path, save_settings,
    settings_file_path,
)
from downloader_app.file_actions import open_folder, play_file
from downloader_app.helpers import display_duration, is_youtube_url
from downloader_app.service import YouTubeService
from downloader_app.thumbnails import fetch_thumbnail
from downloader_app.widgets import DownloadProgress, RoundedButton, RoundedCombobox

class DownloaderApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__(className="YouTubeDownloader")
        self.title(APP_NAME)
        self.geometry("1080x800")
        self.minsize(640, 820)
        self.configure(bg=BG)
        self._icon_image = None
        try:
            self._icon_image = tk.PhotoImage(file=str(resource_path("assets/youtube_downloader.png")))
            self.iconphoto(True, self._icon_image)
        except tk.TclError:
            pass
        self.events: queue.Queue[tuple] = queue.Queue()
        self.cancel_event = threading.Event()
        self.service = YouTubeService(self.events, self.cancel_event)
        self.thumbnail_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="thumbnail")
        self._playlist_generation = 0
        self._thumbnail_photos: dict[int, ImageTk.PhotoImage] = {}
        self._thumbnail_labels: list[tk.Label] = []
        self._downloads_generation = 0
        self._download_thumbnail_photos: dict[int, ImageTk.PhotoImage] = {}
        self._download_thumbnail_labels: list[tk.Label] = []
        self.worker: threading.Thread | None = None
        self.busy = False
        self.settings_path = settings_file_path()
        saved_settings = load_settings(self.settings_path)
        environment_proxy = (os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or
                             os.environ.get("ALL_PROXY") or os.environ.get("all_proxy") or
                             os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or "")
        self.destination = tk.StringVar(value=saved_settings.get("destination", str(DEFAULT_FOLDER)))
        self.quality_choice = tk.StringVar(value=saved_settings.get("quality", "Best available"))
        self.url = tk.StringVar(value=saved_settings.get("url", ""))
        self.proxy = tk.StringVar(value=saved_settings.get("proxy") or environment_proxy or DEFAULT_PROXY)
        saved_urls = saved_settings.get("url_history", [])
        saved_proxies = saved_settings.get("proxy_history", [])
        if not isinstance(saved_urls, list):
            saved_urls = []
        if not isinstance(saved_proxies, list):
            saved_proxies = []
        self.url_history = list(dict.fromkeys(
            value for value in [self.url.get(), *saved_urls]
            if isinstance(value, str) and value.strip()
        ))[:5]
        self.proxy_history = list(dict.fromkeys(
            value for value in [self.proxy.get(), *saved_proxies]
            if isinstance(value, str) and value.strip()
        ))[:20]
        self.proxy_enabled = tk.BooleanVar(value=saved_settings.get("proxy_enabled", True))
        self._url_placeholder_visible = False
        self._settings_save_job = None
        self.select_all_var = tk.BooleanVar(value=False)
        self.playlist_entries: list[dict] = []
        self.selection_vars: list[tk.BooleanVar] = []
        self._style()
        self._build()
        self.proxy_entry.configure(state="normal" if self.proxy_enabled.get() else "disabled")
        for variable in (self.destination, self.url, self.proxy, self.proxy_enabled, self.quality_choice):
            variable.trace_add("write", self._schedule_settings_save)
        self.destination.trace_add("write", lambda *_: self._refresh_downloads())
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._drain_events)
        self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.bind_all("<Button-4>", self._on_mousewheel, add="+")
        self.bind_all("<Button-5>", self._on_mousewheel, add="+")

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL_LIGHT, foreground=ACCENT,
                        padding=(15, 7), font=("TkDefaultFont", 9, "bold"))
        style.map("TNotebook.Tab", background=[("selected", ACCENT), ("active", "#303846")],
                  foreground=[("selected", "white"), ("active", "white")])
        style.configure("TCombobox", fieldbackground=PANEL_LIGHT, background=PANEL_LIGHT,
                        foreground=TEXT, arrowcolor=TEXT, bordercolor=PANEL_LIGHT,
                        lightcolor=PANEL_LIGHT, darkcolor=PANEL_LIGHT, padding=9)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL_LIGHT)],
                  foreground=[("readonly", TEXT)])
        style.configure("Dark.TCombobox", fieldbackground=PANEL_LIGHT, background=PANEL_LIGHT,
                        foreground="white", arrowcolor="white", bordercolor=PANEL_LIGHT,
                        lightcolor=PANEL_LIGHT, darkcolor=PANEL_LIGHT, padding=7, relief="flat")
        style.map("Dark.TCombobox", fieldbackground=[("disabled", PANEL_LIGHT), ("!disabled", PANEL_LIGHT)],
                  foreground=[("disabled", "white"), ("readonly", "white"), ("!disabled", "white")],
                  arrowcolor=[("disabled", "white"), ("!disabled", "white")])
        style.configure("Placeholder.TCombobox", fieldbackground=PANEL_LIGHT, background=PANEL_LIGHT,
                        foreground=MUTED, arrowcolor="white", bordercolor=PANEL_LIGHT,
                        lightcolor=PANEL_LIGHT, darkcolor=PANEL_LIGHT, padding=7, relief="flat")
        style.map("Placeholder.TCombobox", fieldbackground=[("disabled", PANEL_LIGHT), ("!disabled", PANEL_LIGHT)],
                  foreground=[("disabled", MUTED), ("!disabled", MUTED)],
                  arrowcolor=[("disabled", "white"), ("!disabled", "white")])
        self.option_add("*TCombobox*Listbox.background", PANEL_LIGHT)
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.option_add("*TCombobox*Listbox.selectForeground", "white")
        style.configure("Vertical.TScrollbar", troughcolor=PANEL, background=PANEL_LIGHT,
                        bordercolor=PANEL, arrowcolor=MUTED)
        style.configure("Horizontal.TProgressbar", troughcolor=PANEL_LIGHT,
                        background=ACCENT, bordercolor=PANEL_LIGHT, lightcolor=ACCENT,
                        darkcolor=ACCENT, thickness=8)

    def _schedule_settings_save(self, *_args) -> None:
        if self._settings_save_job is not None:
            self.after_cancel(self._settings_save_job)
        self._settings_save_job = self.after(400, self._save_settings)

    def _save_settings(self) -> None:
        self._settings_save_job = None
        settings = {
            "destination": self.destination.get(),
            "quality": self.quality_choice.get(),
            "url": "" if self._url_placeholder_visible else self.url.get(),
            "url_history": self.url_history,
            "proxy": self.proxy.get(),
            "proxy_history": self.proxy_history,
            "proxy_enabled": self.proxy_enabled.get(),
        }
        try:
            save_settings(self.settings_path, settings)
        except OSError:
            pass

    def _show_url_placeholder(self, _event=None) -> None:
        if not self.url.get().strip():
            self._url_placeholder_visible = True
            self.url.set(URL_PLACEHOLDER)
            self.url_entry.configure(foreground=MUTED)

    def _clear_url_placeholder(self, _event=None) -> None:
        if self._url_placeholder_visible:
            self._url_placeholder_visible = False
            if self.url.get() == URL_PLACEHOLDER:
                self.url.set("")
            self.url_entry.configure(foreground="white")

    def _toggle_proxy(self) -> None:
        self.proxy_entry.configure(state="normal" if self.proxy_enabled.get() else "disabled")
        self._schedule_settings_save()

    def _on_close(self) -> None:
        if self._settings_save_job is not None:
            self.after_cancel(self._settings_save_job)
        self._save_settings()
        self.thumbnail_executor.shutdown(wait=False, cancel_futures=True)
        self.destroy()

    def _build(self) -> None:
        root = tk.Frame(self, bg=BG)
        root.pack(fill="both", expand=True, padx=28, pady=22)

        header = tk.Frame(root, bg=BG)
        header.pack(fill="x", pady=(0, 17))
        badge = tk.Canvas(header, width=44, height=44, bg=BG, highlightthickness=0)
        badge.pack(side="left", padx=(0, 13))
        badge.create_rectangle(9, 4, 35, 40, fill=ACCENT, outline="")
        badge.create_rectangle(1, 12, 43, 32, fill=ACCENT, outline="")
        for x, y, start in ((1, 4, 90), (27, 4, 0), (27, 24, 270), (1, 24, 180)):
            badge.create_arc(x, y, x + 16, y + 16, start=start, extent=90,
                             style="pieslice", fill=ACCENT, outline=ACCENT)
        badge.create_polygon(17, 13, 17, 31, 30, 22, fill="white", outline="")
        title_box = tk.Frame(header, bg=BG)
        title_box.pack(side="left", anchor="center")
        tk.Label(title_box, text="Video Downloader", bg=BG, fg=TEXT,
                 font=("TkDefaultFont", 21, "bold")).pack(anchor="w")
        tk.Label(title_box, text="Choose videos from a playlist and download only what you select",
                 bg=BG, fg=MUTED, font=("TkDefaultFont", 10)).pack(anchor="w", pady=(2, 0))

        link_card = tk.Frame(root, bg=PANEL, padx=14, pady=13)
        link_card.pack(fill="x", pady=(0, 16))
        tk.Label(link_card, text="YouTube video or playlist link", bg=PANEL, fg=TEXT,
                 font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(0, 8))
        link_row = tk.Frame(link_card, bg=PANEL)
        link_row.pack(fill="x")
        self.url_entry = RoundedCombobox(link_row, textvariable=self.url, values=self.url_history,
                                         state="normal", style="Dark.TCombobox", font=("TkDefaultFont", 11))
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.url_entry.bind("<Control-v>", lambda _e: self.after(80, self._trim_url))
        self.url_entry.bind("<FocusIn>", self._clear_url_placeholder)
        self.url_entry.bind("<FocusOut>", self._show_url_placeholder)
        self.url_entry.bind("<<HistorySelected>>", self._clear_url_placeholder)
        if not self.url.get():
            self._show_url_placeholder()
        self._button(link_row, "Paste", self._paste).pack(side="right", padx=(0, 8))
        self.load_button = self._button(link_row, "Load videos", self._load_playlist, primary=True)
        self.load_button.pack(side="right")
        proxy_row = tk.Frame(link_card, bg=PANEL)
        proxy_row.pack(fill="x", pady=(9, 0))
        self.proxy_check = tk.Checkbutton(
            proxy_row, text="Use proxy", variable=self.proxy_enabled, command=self._toggle_proxy,
            bg=PANEL, fg=MUTED, activebackground=PANEL, activeforeground=TEXT,
            selectcolor=BG, relief="flat", highlightthickness=0, cursor="hand2",
            font=("TkDefaultFont", 9),
        )
        self.proxy_check.pack(side="left", padx=(0, 8))
        self.proxy_entry = RoundedCombobox(proxy_row, textvariable=self.proxy, values=self.proxy_history,
                                           state="normal", style="Dark.TCombobox", font=("TkDefaultFont", 9))
        self.proxy_entry.pack(side="left", fill="x", expand=True)

        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True)

        sidebar = tk.Frame(body, bg=PANEL, width=218, padx=15, pady=15)
        sidebar.pack(side="left", fill="y", padx=(0, 14))
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text="DOWNLOAD SELECTED", bg=PANEL, fg=MUTED,
                 font=("TkDefaultFont", 9, "bold")).pack(anchor="w", pady=(0, 9))
        self.video_button = self._button(sidebar, "↓  Download video", lambda: self._start_download("video"), primary=True)
        self.video_button.pack(fill="x", pady=(0, 8))
        self.mp3_button = self._button(sidebar, "♫  Download MP3", lambda: self._start_download("mp3"))
        self.mp3_button.pack(fill="x", pady=(0, 8))
        self.mp3_button.pack_configure(pady=(0, 18))

        tk.Label(sidebar, text="VIDEO QUALITY", bg=PANEL, fg=MUTED,
                 font=("TkDefaultFont", 9, "bold")).pack(anchor="w")
        self.quality_box = ttk.Combobox(sidebar, state="readonly", textvariable=self.quality_choice,
                                        values=("Best available", "1080p", "720p", "480p"),
                                        font=("TkDefaultFont", 10))
        self.quality_box.pack(fill="x", pady=(7, 18))

        tk.Label(sidebar, text="SAVE TO", bg=PANEL, fg=MUTED,
                 font=("TkDefaultFont", 9, "bold")).pack(anchor="w")
        self.folder_label = tk.Label(sidebar, textvariable=self.destination, bg=PANEL, fg=TEXT,
                                     font=("TkDefaultFont", 9), anchor="w", justify="left",
                                     wraplength=184)
        self.folder_label.pack(fill="x", pady=(7, 9))
        self._button(sidebar, "Choose folder", self._choose_folder).pack(fill="x")
        self._button(sidebar, "Open Folder", self._open_destination_folder).pack(fill="x", pady=(6, 0))

        list_card = tk.Frame(body, bg=PANEL, padx=15, pady=13)
        list_card.pack(side="left", fill="both", expand=True)
        self.content_tabs = ttk.Notebook(list_card)
        self.content_tabs.pack(fill="both", expand=True)
        playlist_tab = tk.Frame(self.content_tabs, bg=PANEL)
        downloads_tab = tk.Frame(self.content_tabs, bg=PANEL)
        self.content_tabs.add(playlist_tab, text="Playlist")
        self.content_tabs.add(downloads_tab, text="Downloads")
        self.downloads_tab = downloads_tab
        list_header = tk.Frame(playlist_tab, bg=PANEL)
        list_header.pack(fill="x", pady=(0, 8))
        title_group = tk.Frame(list_header, bg=PANEL)
        title_group.pack(side="left", fill="x", expand=True)
        tk.Label(title_group, text="Playlist videos", bg=PANEL, fg=TEXT,
                 font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        self.list_status_var = tk.StringVar(value="Paste a playlist link and select Load videos")
        tk.Label(title_group, textvariable=self.list_status_var, bg=PANEL, fg=MUTED,
                 font=("TkDefaultFont", 9)).pack(anchor="w", pady=(3, 0))

        select_row = tk.Frame(playlist_tab, bg=PANEL_LIGHT, padx=9, pady=5)
        select_row.pack(fill="x", pady=(0, 8))
        self.select_all_check = tk.Checkbutton(
            select_row, text="Select all", variable=self.select_all_var,
            command=self._toggle_all, bg=PANEL_LIGHT, fg=TEXT,
            activebackground=PANEL_LIGHT, activeforeground=TEXT,
            selectcolor=BG, font=("TkDefaultFont", 9, "bold"), relief="flat",
            highlightthickness=0, cursor="hand2",
        )
        self.select_all_check.pack(side="left")
        self.selected_count_var = tk.StringVar(value="0 selected")
        tk.Label(select_row, textvariable=self.selected_count_var, bg=PANEL_LIGHT, fg=MUTED,
                 font=("TkDefaultFont", 9)).pack(side="right")

        list_area = tk.Frame(playlist_tab, bg=PANEL)
        list_area.pack(fill="both", expand=True)
        self.list_canvas = tk.Canvas(list_area, bg=PANEL, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(list_area, orient="vertical", command=self.list_canvas.yview)
        self.list_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.list_canvas.pack(side="left", fill="both", expand=True)
        self.list_inner = tk.Frame(self.list_canvas, bg=PANEL)
        self.list_window = self.list_canvas.create_window((0, 0), window=self.list_inner, anchor="nw")
        self.list_inner.bind("<Configure>", self._update_scroll_region)
        self.list_canvas.bind("<Configure>", self._resize_list_inner)
        self._show_empty_message("No videos loaded yet")

        downloads_header = tk.Frame(downloads_tab, bg=PANEL)
        downloads_header.pack(fill="x", pady=(0, 8))
        tk.Label(downloads_header, text="Saved media files", bg=PANEL, fg=TEXT,
                 font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        self.downloads_status_var = tk.StringVar(value="Files in the selected download folder")
        tk.Label(downloads_header, textvariable=self.downloads_status_var, bg=PANEL, fg=MUTED,
                 font=("TkDefaultFont", 9)).pack(anchor="w", pady=(3, 0))
        downloads_area = tk.Frame(downloads_tab, bg=PANEL)
        downloads_area.pack(fill="both", expand=True)
        self.downloads_canvas = tk.Canvas(downloads_area, bg=PANEL, highlightthickness=0, bd=0)
        downloads_scroll = ttk.Scrollbar(downloads_area, orient="vertical", command=self.downloads_canvas.yview)
        self.downloads_canvas.configure(yscrollcommand=downloads_scroll.set)
        downloads_scroll.pack(side="right", fill="y")
        self.downloads_canvas.pack(side="left", fill="both", expand=True)
        self.downloads_inner = tk.Frame(self.downloads_canvas, bg=PANEL)
        self.downloads_window = self.downloads_canvas.create_window((0, 0), window=self.downloads_inner, anchor="nw")
        self.downloads_inner.bind("<Configure>", self._update_downloads_scroll_region)
        self.downloads_canvas.bind("<Configure>", self._resize_downloads_inner)
        self._refresh_downloads()

        footer = tk.Frame(root, bg=BG)
        footer.pack(fill="x", pady=(13, 0))
        self.status_var = tk.StringVar(value="Ready when you are")
        status_card = tk.Frame(footer, bg=PANEL, padx=13, pady=10)
        status_card.pack(side="left", fill="x", expand=True)
        status_line = tk.Frame(status_card, bg=PANEL)
        status_line.pack(fill="x", pady=(0, 7))
        tk.Label(status_line, textvariable=self.status_var, bg=PANEL, fg=TEXT,
                 font=("TkDefaultFont", 9)).pack(side="left")
        self.progress = DownloadProgress(status_card)
        self.progress.pack(fill="x")
        self.cancel_button = self._button(footer, "Cancel", self._cancel, style="text")

        tk.Label(root, text="Only download content you own or have permission to save.", bg=BG,
                 fg=MUTED, font=("TkDefaultFont", 9)).pack(anchor="w", pady=(9, 0))
        tk.Label(root, text="Developed by Shamim", bg=BG, fg=MUTED,
                 font=("TkDefaultFont", 9)).pack(anchor="e")

    @staticmethod
    def _button(parent, text: str, command, primary: bool = False, style: str = "secondary", width: int = 120, subtle: bool = False):
        return RoundedButton(parent, text, command, primary=primary, subtle=subtle or style == "text", width=width)

    def _show_empty_message(self, text: str) -> None:
        for child in self.list_inner.winfo_children():
            child.destroy()
        tk.Label(self.list_inner, text=text, bg=PANEL, fg=MUTED,
                 font=("TkDefaultFont", 10), pady=30).pack(fill="x")

    def _resize_list_inner(self, event) -> None:
        self.list_canvas.itemconfigure(self.list_window, width=event.width)

    def _update_scroll_region(self, _event=None) -> None:
        self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all"))

    def _resize_downloads_inner(self, event) -> None:
        self.downloads_canvas.itemconfigure(self.downloads_window, width=event.width)

    def _update_downloads_scroll_region(self, _event=None) -> None:
        self.downloads_canvas.configure(scrollregion=self.downloads_canvas.bbox("all"))

    def _refresh_downloads(self) -> None:
        if not hasattr(self, "downloads_inner"):
            return
        self._downloads_generation += 1
        generation = self._downloads_generation
        self._download_thumbnail_photos.clear()
        self._download_thumbnail_labels = []
        for child in self.downloads_inner.winfo_children():
            child.destroy()
        folder = Path(self.destination.get()).expanduser()
        extensions = {".mp4", ".mkv", ".webm", ".mp3", ".m4a", ".mov", ".avi", ".wav", ".flac"}
        try:
            files = sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in extensions),
                           key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            files = []
        if not files:
            tk.Label(self.downloads_inner, text="No media files found in this download folder",
                     bg=PANEL, fg=MUTED, font=("TkDefaultFont", 10), pady=30).pack(fill="x")
        for index, path in enumerate(files):
            row_bg = PANEL if index % 2 == 0 else "#1c222c"
            row = tk.Frame(self.downloads_inner, bg=row_bg, padx=7, pady=5)
            row.pack(fill="x")
            thumbnail = tk.Label(row, bg=PANEL_LIGHT, width=12, height=4, bd=0)
            thumbnail.pack(side="left", padx=(0, 9))
            self._download_thumbnail_labels.append(thumbnail)
            video_id = re.search(r"\[([A-Za-z0-9_-]{11})\]", path.stem)
            if video_id:
                image_proxy = self.proxy.get().strip() if self.proxy_enabled.get() else ""
                thumbnail_url = f"https://i.ytimg.com/vi/{video_id.group(1)}/hqdefault.jpg"
                fallback_url = f"https://i.ytimg.com/vi/{video_id.group(1)}/default.jpg"
                self.thumbnail_executor.submit(
                    self._fetch_download_thumbnail, generation, index,
                    thumbnail_url, image_proxy, fallback_url,
                )
            self._button(row, "Play", lambda p=path: self._play_download(p), width=64).pack(side="right", padx=(4, 0))
            self._button(row, "Delete", lambda p=path: self._delete_download(p), subtle=True, width=68).pack(side="right", padx=(4, 0))
            name = tk.Label(row, text=path.name, bg=row_bg, fg=TEXT, anchor="w",
                            justify="left", wraplength=430, font=("TkDefaultFont", 9))
            name.pack(side="left", fill="x", expand=True, padx=(2, 8))
        self.downloads_status_var.set(f"{len(files)} media file" + ("s" if len(files) != 1 else "") + f" in {folder}")

    def _on_mousewheel(self, event):
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget in (self.list_canvas, self.list_inner):
                canvas = self.list_canvas
                break
            if widget in (self.downloads_canvas, self.downloads_inner):
                canvas = self.downloads_canvas
                break
            widget = getattr(widget, "master", None)
        else:
            return

        if getattr(event, "num", None) == 4:
            direction = -1
        elif getattr(event, "num", None) == 5:
            direction = 1
        else:
            delta = getattr(event, "delta", 0)
            direction = -1 if delta > 0 else 1
            if delta and abs(delta) >= 120:
                direction = -int(delta / 120)
        canvas.yview_scroll(direction, "units")
        return "break"

    def _fetch_download_thumbnail(self, generation: int, index: int, url: str,
                                  proxy: str, fallback_url: str) -> None:
        data = fetch_thumbnail(url, proxy, fallback_url)
        if data:
            self.events.put(("download_thumbnail_loaded", generation, index, data))

    def _show_download_thumbnail(self, generation: int, index: int, data: bytes) -> None:
        if generation != self._downloads_generation or index >= len(self._download_thumbnail_labels):
            return
        try:
            with Image.open(BytesIO(data)) as source:
                thumbnail = ImageOps.fit(source.convert("RGB"), (128, 72), method=Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(thumbnail)
            self._download_thumbnail_photos[index] = photo
            self._download_thumbnail_labels[index].configure(image=photo, width=128, height=72)
        except (OSError, tk.TclError, ValueError):
            pass

    def _play_download(self, path: Path) -> None:
        try:
            play_file(path)
        except OSError as exc:
            messagebox.showerror("Could not play file", str(exc))

    def _open_destination_folder(self) -> None:
        folder = Path(self.destination.get()).expanduser()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            open_folder(folder)
        except OSError as exc:
            messagebox.showerror("Could not open folder", str(exc))

    def _delete_download(self, path: Path) -> None:
        if not messagebox.askyesno("Delete downloaded file", f"Delete this file permanently?\n\n{path.name}"):
            return
        try:
            path.unlink()
        except OSError as exc:
            messagebox.showerror("Could not delete file", str(exc))
        self._refresh_downloads()

    def _paste(self) -> None:
        self._clear_url_placeholder()
        try:
            self.url.set(self.clipboard_get().strip())
            self.url_entry.icursor("end")
        except tk.TclError:
            self.status_var.set("Clipboard is empty")

    def _trim_url(self) -> None:
        if not self._url_placeholder_visible:
            self.url.set(self.url.get().strip())

    def _choose_folder(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.destination.get(), title="Choose download folder")
        if selected:
            self.destination.set(selected)
            self._refresh_downloads()

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.load_button.configure(state="disabled" if busy else "normal")
        state = "disabled" if busy else "normal"
        for button in (self.video_button, self.mp3_button):
            button.configure(state=state)
        self.select_all_check.configure(state=state)
        for child in self.list_inner.winfo_children():
            for widget in child.winfo_children():
                if isinstance(widget, tk.Checkbutton):
                    widget.configure(state=state)

    def _remember_url(self, value: str) -> None:
        self.url_history = [value] + [item for item in self.url_history if item != value]
        self.url_history = self.url_history[:5]
        self.url_entry.configure(values=self.url_history)
        self._schedule_settings_save()

    def _remember_proxy(self, value: str) -> None:
        if not value:
            return
        self.proxy_history = [value] + [item for item in self.proxy_history if item != value]
        self.proxy_history = self.proxy_history[:20]
        self.proxy_entry.configure(values=self.proxy_history)
        self._schedule_settings_save()

    def _load_playlist(self) -> None:
        link = "" if self._url_placeholder_visible else self.url.get().strip()
        if not is_youtube_url(link):
            messagebox.showerror("Check the link", "Enter a valid YouTube video or playlist link.")
            self.url_entry.focus_set()
            return
        if not importlib.util.find_spec("yt_dlp"):
            messagebox.showerror("Setup needed", "yt-dlp is not installed in this Python environment.\n\nFrom the app folder, run:\nuv sync")
            return
        self._remember_url(link)
        self._set_busy(True)
        self.list_status_var.set("Loading playlist videos…")
        self.status_var.set("Reading playlist…")
        self._show_empty_message("Loading videos…")
        proxy = self.proxy.get().strip() if self.proxy_enabled.get() else ""
        self._remember_proxy(proxy)
        self.worker = threading.Thread(target=self._read_playlist, args=(link, proxy), daemon=True)
        self.worker.start()

    def _read_playlist(self, link: str, proxy: str = "") -> None:
        self.service.read_playlist(link, proxy)

    def _render_playlist(self, title: str, entries: list[dict], proxy: str = "") -> None:
        self.playlist_entries = entries
        self.selection_vars = []
        self.select_all_var.set(False)
        for child in self.list_inner.winfo_children():
            child.destroy()
        self._playlist_generation += 1
        generation = self._playlist_generation
        self._thumbnail_photos.clear()
        self._thumbnail_labels = []
        for index, entry in enumerate(entries):
            row_bg = PANEL if index % 2 == 0 else "#1c222c"
            row = tk.Frame(self.list_inner, bg=row_bg, padx=5, pady=4)
            row.pack(fill="x")
            selected = tk.BooleanVar(value=bool(
                self._existing_files_for_entry(Path(self.destination.get()).expanduser(), entry)
            ))
            self.selection_vars.append(selected)
            check = tk.Checkbutton(
                row, variable=selected, command=self._update_selection_count,
                bg=row_bg, fg=TEXT, activebackground=row_bg, activeforeground=TEXT,
                selectcolor=BG, relief="flat", highlightthickness=0, cursor="hand2",
            )
            check.pack(side="left", padx=(1, 7))
            thumbnail = tk.Label(row, bg=PANEL_LIGHT, width=16, height=4, bd=0)
            thumbnail.pack(side="left", padx=(0, 9))
            self._thumbnail_labels.append(thumbnail)
            thumbnail_url = entry.get("thumbnail")
            if thumbnail_url:
                image_proxy = proxy if proxy else (self.proxy.get().strip() if self.proxy_enabled.get() else "")
                self.thumbnail_executor.submit(
                    self._fetch_thumbnail, generation, index, thumbnail_url, image_proxy,
                    entry.get("thumbnail_fallback"),
                )
            text_box = tk.Frame(row, bg=row_bg)
            text_box.pack(side="left", fill="x", expand=True, pady=5)
            tk.Label(text_box, text=entry["title"], bg=row_bg, fg=TEXT, anchor="w",
                     justify="left", wraplength=650, font=("TkDefaultFont", 9)).pack(fill="x", anchor="w")
            duration = display_duration(entry.get("duration"))
            if duration:
                tk.Label(row, text=duration, bg=row_bg, fg=MUTED,
                         font=("TkDefaultFont", 9)).pack(side="right", padx=(8, 6))
        if not entries:
            self._show_empty_message("No downloadable videos were found in this playlist")
        self.list_status_var.set(f"{title} · {len(entries)} video" + ("s" if len(entries) != 1 else ""))
        self._update_selection_count()
        self.list_canvas.yview_moveto(0)
        self._set_busy(False)
        self.status_var.set("Select videos to download")

    def _fetch_thumbnail(self, generation: int, index: int, url: str, proxy: str,
                         fallback_url: str | None = None) -> None:
        data = fetch_thumbnail(url, proxy, fallback_url)
        if data:
            self.events.put(("thumbnail_loaded", generation, index, data))

    def _show_thumbnail(self, generation: int, index: int, data: bytes) -> None:
        if generation != self._playlist_generation or index >= len(self._thumbnail_labels):
            return
        try:
            with Image.open(BytesIO(data)) as source:
                thumbnail = ImageOps.fit(source.convert("RGB"), (128, 72), method=Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(thumbnail)
            self._thumbnail_photos[index] = photo
            self._thumbnail_labels[index].configure(image=photo, width=128, height=72)
        except (OSError, tk.TclError, ValueError):
            pass

    def _toggle_all(self) -> None:
        value = self.select_all_var.get()
        for selected in self.selection_vars:
            selected.set(value)
        self._update_selection_count()

    def _update_selection_count(self) -> None:
        selected_count = sum(1 for selected in self.selection_vars if selected.get())
        total = len(self.selection_vars)
        self.selected_count_var.set(f"{selected_count} of {total} selected")
        self.select_all_var.set(bool(total) and selected_count == total)

    @staticmethod
    def _existing_files_for_entry(folder: Path, entry: dict) -> list[Path]:
        video_id = entry.get("id")
        if not video_id:
            return []
        marker = re.escape(f"[{video_id}]")
        try:
            return [
                path for path in folder.iterdir()
                if path.is_file() and re.search(rf"{marker}(?:\d+)?$", path.stem)
            ]
        except OSError:
            return []

    @classmethod
    def _next_duplicate_suffix(cls, folder: Path, entry: dict, reserved: set[int]) -> int:
        video_id = entry.get("id")
        marker = re.escape(f"[{video_id}]")
        used = set(reserved)
        for path in cls._existing_files_for_entry(folder, entry):
            match = re.search(rf"{marker}(\d+)$", path.stem)
            if match:
                used.add(int(match.group(1)))
            else:
                used.add(0)
        suffix = 1
        while suffix in used:
            suffix += 1
        reserved.add(suffix)
        return suffix

    def _start_download(self, mode: str) -> None:
        selected = [entry for entry, var in zip(self.playlist_entries, self.selection_vars) if var.get()]
        if not selected:
            messagebox.showinfo("Nothing selected", "Select one or more playlist videos first.")
            return
        if not importlib.util.find_spec("yt_dlp"):
            messagebox.showerror("Setup needed", "yt-dlp is not installed in this Python environment.\n\nFrom the app folder, run:\nuv sync")
            return
        folder = Path(self.destination.get()).expanduser()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Folder unavailable", str(exc))
            return
        download_items = []
        reserved_suffixes: dict[str, set[int]] = {}
        for entry in selected:
            existing_files = self._existing_files_for_entry(folder, entry)
            item = dict(entry)
            if existing_files:
                if not messagebox.askyesno(
                    "Already downloaded",
                    f"{entry['title']} is already in the download folder as "
                    f"{existing_files[0].name}.\n\nDownload another copy with a numbered name?",
                ):
                    continue
                video_id = str(entry.get("id") or entry["title"])
                reserved = reserved_suffixes.setdefault(video_id, set())
                item["duplicate_suffix"] = self._next_duplicate_suffix(folder, entry, reserved)
            download_items.append(item)
        if not download_items:
            self.status_var.set("No downloads started · existing files skipped")
            return
        selected = download_items
        self.cancel_event.clear()
        self.progress.configure(value=0)
        self._set_busy(True)
        self.cancel_button.pack(side="right", padx=(10, 0))
        quality = self.quality_choice.get()
        proxy = self.proxy.get().strip() if self.proxy_enabled.get() else ""
        self._remember_proxy(proxy)
        self.worker = threading.Thread(
            target=self._download_selected, args=(selected, folder, mode, quality, proxy), daemon=True
        )
        self.worker.start()

    def _download_selected(self, entries: list[dict], folder: Path, mode: str, quality: str, proxy: str = "") -> None:
        self.service.download_selected(entries, folder, mode, quality, proxy)

    def _cancel(self) -> None:
        self.cancel_event.set()
        self.cancel_button.configure(state="disabled", text="Cancelling…")
        self.status_var.set("Stopping after the current transfer…")

    def _drain_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "playlist_loaded":
                    _, title, entries, proxy = event
                    self._render_playlist(title, entries, proxy)
                elif kind == "thumbnail_loaded":
                    _, generation, index, data = event
                    self._show_thumbnail(generation, index, data)
                elif kind == "download_thumbnail_loaded":
                    _, generation, index, data = event
                    self._show_download_thumbnail(generation, index, data)
                elif kind == "playlist_error":
                    _, detail = event
                    self._set_busy(False)
                    self.list_status_var.set("Could not load playlist")
                    self._show_empty_message("Playlist could not be loaded")
                    self.status_var.set("Playlist loading failed")
                    messagebox.showerror("Could not load playlist", detail[-1400:])
                elif kind == "download_item":
                    _, index, total, title = event
                    self.progress.configure(value=0)
                    self.status_var.set(f"Video {index} of {total}: {title}")
                elif kind == "download_status":
                    _, index, total, status = event
                    self.status_var.set(f"Video {index} of {total}: {status}")
                elif kind == "progress":
                    _, index, total, percent, speed, eta = event
                    self.progress.configure(value=percent)
                    speed_text = f" · {speed / 1024 / 1024:.1f} MB/s" if speed else ""
                    eta_text = f" · {eta}s left" if eta else ""
                    self.status_var.set(f"Video {index} of {total}: Downloading{speed_text}{eta_text}")
                elif kind == "item_complete":
                    _, index, total, completed, failed_count = event
                    self.status_var.set(f"Processed {index} of {total} · {completed} downloaded · {failed_count} failed")
                elif kind == "download_finished":
                    _, completed, total, failed, cancelled = event
                    self._set_busy(False)
                    self.cancel_button.pack_forget()
                    self.cancel_button.configure(state="normal", text="Cancel")
                    self._refresh_downloads()
                    self.progress.configure(value=100 if completed == total else 0)
                    if cancelled:
                        self.status_var.set(f"Cancelled · {completed} of {total} downloaded")
                    elif failed:
                        self.status_var.set(f"Finished · {completed} of {total} downloaded, {len(failed)} failed")
                        failed_text = "\n".join(f"• {title}: {detail[-220:]}" if detail else f"• {title}" for title, detail in failed[:8])
                        if len(failed) > 8:
                            failed_text += f"\n…and {len(failed) - 8} more"
                        messagebox.showwarning("Some downloads failed", failed_text)
                    else:
                        self.status_var.set(f"All done · {completed} videos downloaded")
        except queue.Empty:
            pass
        self.after(100, self._drain_events)


if __name__ == "__main__":
    DownloaderApp().mainloop()
