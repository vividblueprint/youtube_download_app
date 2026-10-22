"""Reusable rounded Tkinter controls."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .config import ACCENT, MUTED, PANEL, PANEL_LIGHT

class RoundedButton(tk.Canvas):
    def __init__(self, parent, text: str, command, primary: bool = False, subtle: bool = False, width: int = 120):
        self._enabled = True
        self._text = text
        self._command = command
        self._primary = primary
        self._subtle = subtle
        self._hovered = False
        self._base = ACCENT if primary else (PANEL if subtle else PANEL_LIGHT)
        self._foreground = "white" if primary else (MUTED if subtle else "#f4f6f8")
        parent_bg = parent.cget("bg")
        super().__init__(parent, width=width, height=36, bg=parent_bg, bd=0, highlightthickness=0, cursor="hand2")
        super().bind("<Configure>", self._draw)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._activate)
        self._draw()

    def configure(self, cnf=None, **kwargs):
        state = kwargs.pop("state", None)
        text = kwargs.pop("text", None)
        result = super().configure(cnf, **kwargs)
        if text is not None:
            self._text = text
        if state is not None:
            self._enabled = state != "disabled"
            super().configure(cursor="hand2" if self._enabled else "arrow")
        if state is not None or text is not None:
            self._draw()
        return result

    config = configure

    def _on_enter(self, _event=None) -> None:
        self._hovered = True
        self._draw()

    def _on_leave(self, _event=None) -> None:
        self._hovered = False
        self._draw()

    def _activate(self, _event=None) -> None:
        if self._enabled and self._command:
            self._command()

    def _draw(self, _event=None) -> None:
        self.delete("all")
        width = max(self.winfo_width(), 40)
        height = max(self.winfo_height(), 30)
        inset = 1
        radius = min(9, (height - inset * 2) // 2)
        color = self._base
        if not self._enabled:
            color = "#343a43"
        elif self._hovered and not self._primary:
            color = "#303846"
        elif self._hovered:
            color = "#ee4052"
        x0, y0, x1, y1 = inset, inset, width - inset, height - inset
        self.create_rectangle(x0 + radius, y0, x1 - radius, y1, fill=color, outline=color)
        self.create_rectangle(x0, y0 + radius, x1, y1 - radius, fill=color, outline=color)
        corners = [(x0, y0, 90), (x1 - 2 * radius, y0, 0), (x1 - 2 * radius, y1 - 2 * radius, 270), (x0, y1 - 2 * radius, 180)]
        for x, y, start in corners:
            self.create_arc(x, y, x + 2 * radius, y + 2 * radius, start=start, extent=90,
                            style="pieslice", fill=color, outline=color)
        foreground = self._foreground if self._enabled else "#9299a2"
        self.create_text(width / 2, height / 2, text=self._text, fill=foreground,
                         font=("TkDefaultFont", 9, "bold" if self._primary else "normal"))


class DownloadProgress(tk.Canvas):
    """Red progress bar with its percentage rendered over the fill."""
    def __init__(self, parent):
        self.value = 0.0
        super().__init__(parent, height=18, bg=PANEL, bd=0, highlightthickness=0)
        super().bind("<Configure>", self._draw)
        self._draw()

    def configure(self, cnf=None, **kwargs):
        if cnf:
            kwargs = {**cnf, **kwargs}
        value = kwargs.pop("value", None)
        result = super().configure(**kwargs)
        if value is not None:
            self.value = max(0.0, min(100.0, float(value)))
            self._draw()
        return result

    config = configure

    def _draw(self, _event=None):
        self.delete("all")
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        self.create_rectangle(0, 0, width, height, fill=PANEL_LIGHT, outline="")
        fill_width = width * self.value / 100
        if fill_width > 0:
            self.create_rectangle(0, 0, fill_width, height, fill=ACCENT, outline="")
        self.create_text(width / 2, height / 2, text=f"{self.value:.0f}%", fill="white",
                         font=("TkDefaultFont", 9, "bold"))


class RoundedCombobox(tk.Frame):
    """Editable native entry with a history menu, inset in a softly rounded field."""
    def __init__(self, parent, *, textvariable, values=(), state="normal", style="Dark.TCombobox", font=None):
        self._fill = PANEL_LIGHT
        self._parent_bg = parent.cget("bg")
        self._values = list(values)
        self._state = state
        super().__init__(parent, bg=self._parent_bg, height=44, bd=0, highlightthickness=0)
        self.pack_propagate(False)
        self.canvas = tk.Canvas(self, bg=self._parent_bg, bd=0, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.combo = tk.Entry(
            self, textvariable=textvariable, state=state, bg=PANEL_LIGHT,
            fg="white", insertbackground="white", selectbackground=ACCENT,
            selectforeground="white", relief="flat", bd=0, highlightthickness=0,
            font=font,
        )
        self.combo.place(x=9, y=7, relwidth=1.0, width=-43, height=30)
        self.history_popup = None
        self.history_list = None
        top = self.winfo_toplevel()
        top.bind("<Configure>", self._reposition_history_popup, add="+")
        top.bind_all("<Button-1>", self._dismiss_history_on_click, add="+")
        self.history_button = tk.Button(
            self, text="▾", command=self._show_history, bg=PANEL_LIGHT, fg=MUTED,
            activebackground=PANEL_LIGHT, activeforeground="white",
            relief="flat", bd=0, highlightthickness=0, cursor="hand2", takefocus=0,
        )
        self.history_button.place(relx=1.0, x=-34, y=5, width=27, height=34)
        # Use Tk's window stacking command (Canvas.lower is a different item API).
        self.canvas.tk.call("lower", self.canvas._w)
        self.combo.tk.call("raise", self.combo._w)
        self.history_button.tk.call("raise", self.history_button._w)
        self.bind("<Configure>", self._draw)
        self._draw()

    def configure(self, cnf=None, **kwargs):
        combo = self.__dict__.get("combo")
        if combo is None:
            return super().configure(cnf, **kwargs)
        if cnf:
            kwargs = {**cnf, **kwargs}
        values = kwargs.pop("values", None)
        kwargs.pop("style", None)
        if values is not None:
            self._values = list(values)
            self._refresh_history_list()
        if "state" in kwargs:
            self._state = kwargs["state"]
            self.history_button.configure(state="disabled" if self._state == "disabled" else "normal")
        return combo.configure(**kwargs)

    config = configure

    def bind(self, sequence=None, func=None, add=None):
        combo = self.__dict__.get("combo")
        if combo is None:
            return super().bind(sequence, func, add)
        return combo.bind(sequence, func, add)

    def focus_set(self):
        self.combo.focus_set()

    def _show_history(self):
        if self._state == "disabled":
            return
        if self.history_popup is None or not self.history_popup.winfo_exists():
            self.history_popup = tk.Toplevel(self)
            self.history_popup.overrideredirect(True)
            self.history_popup.transient(self.winfo_toplevel())
            self.history_list = tk.Listbox(
                self.history_popup, height=5, bg=PANEL_LIGHT, fg="white",
                selectbackground=ACCENT, selectforeground="white",
                activestyle="none", relief="solid", bd=1,
                highlightthickness=0, font=self.combo.cget("font"),
            )
            self.history_list.pack(fill="both", expand=True)
            self.history_list.bind("<ButtonRelease-1>", self._select_history_row)
            self.history_list.bind("<Return>", self._select_history_row)
            self.history_list.bind("<Escape>", lambda _event: self._hide_history())
            self.history_list.bind("<Motion>", self._hover_history_row)
            self.history_list.bind("<Leave>", self._clear_history_hover)
        self._refresh_history_list()
        self._reposition_history_popup()
        self.history_popup.deiconify()
        self.history_popup.lift()
        self.history_list.focus_set()

    def _reposition_history_popup(self, _event=None):
        if self.history_popup is None or not self.history_popup.winfo_exists():
            return
        if self.history_popup.state() == "withdrawn":
            return
        width = max(self.combo.winfo_width() + 43, 180)
        height = max(30, min(5, max(1, len(self._values))) * 28)
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        self.history_popup.geometry(f"{width}x{height}+{x}+{y}")

    def _refresh_history_list(self):
        if self.history_list is None or not self.history_list.winfo_exists():
            return
        self.history_list.delete(0, "end")
        values = self._values or ["No recent URLs"]
        for value in values:
            self.history_list.insert("end", value)
            self.history_list.itemconfigure("end", background=PANEL_LIGHT, foreground="white")
        if not self._values:
            self.history_list.configure(state="disabled")
        else:
            self.history_list.configure(state="normal")

    def _hover_history_row(self, event):
        if not self._values:
            return
        index = self.history_list.nearest(event.y)
        self._clear_history_hover()
        if 0 <= index < len(self._values):
            self.history_list.itemconfigure(index, background=ACCENT, foreground="white")
            self._hovered_history_index = index

    def _clear_history_hover(self, _event=None):
        index = getattr(self, "_hovered_history_index", None)
        if index is not None and self.history_list is not None and self.history_list.winfo_exists():
            if index < self.history_list.size():
                self.history_list.itemconfigure(index, background=PANEL_LIGHT, foreground="white")
        self._hovered_history_index = None

    def _select_history_row(self, _event=None):
        selected = self.history_list.curselection()
        if not selected or not self._values:
            return "break"
        self._choose_history(self._values[selected[0]])
        return "break"

    def _hide_history(self):
        if self.history_popup is not None and self.history_popup.winfo_exists():
            self.history_popup.withdraw()

    def _dismiss_history_on_click(self, event):
        if self.history_popup is None or not self.history_popup.winfo_exists():
            return
        if self.history_popup.state() == "withdrawn":
            return
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget is self or widget is self.history_popup:
                return
            widget = getattr(widget, "master", None)
        self._hide_history()

    def _choose_history(self, value):
        self.combo.delete(0, "end")
        self.combo.insert(0, value)
        self.combo.icursor("end")
        self.combo.focus_set()
        self.combo.event_generate("<<HistorySelected>>")
        self._hide_history()

    def __getattr__(self, name):
        combo = self.__dict__.get("combo")
        if combo is not None:
            return getattr(combo, name)
        raise AttributeError(name)

    def _draw(self, _event=None):
        if not hasattr(self, "canvas"):
            return
        self.canvas.delete("all")
        width = max(self.winfo_width(), 80)
        height = max(self.winfo_height(), 36)
        x0, y0, x1, y1 = 1, 1, width - 1, height - 1
        radius = min(12, (height - 2) // 2)
        self.canvas.create_rectangle(x0 + radius, y0, x1 - radius, y1, fill=self._fill, outline=self._fill)
        self.canvas.create_rectangle(x0, y0 + radius, x1, y1 - radius, fill=self._fill, outline=self._fill)
        for x, y, start in ((x0, y0, 90), (x1 - 2 * radius, y0, 0),
                            (x1 - 2 * radius, y1 - 2 * radius, 270), (x0, y1 - 2 * radius, 180)):
            self.canvas.create_arc(x, y, x + 2 * radius, y + 2 * radius, start=start, extent=90,
                                   style="pieslice", fill=self._fill, outline=self._fill)
