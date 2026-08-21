#!/usr/bin/env python
"""Open Rails Shape Packer - a focused front-end for ORZIP.

The interface intentionally exposes the normal model-builder workflow only:
scan a folder for .S shape files, compress/uncompress selected files, or let
Open Rails Shape Packer choose the needed operation from each file's detected state.
"""
from __future__ import annotations

import configparser
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from tkinter import BOTH, BOTTOM, END, LEFT, RIGHT, VERTICAL, X, Y, BooleanVar, Button, Canvas, Checkbutton, Entry, Frame, Label, LabelFrame, Listbox, Menu, PhotoImage, Radiobutton, StringVar, Tk, Toplevel, filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

APP_NAME = "Open Rails Shape Packer"
APP_VERSION = "1.0.1"
UNCOMPRESSED_MAGIC = "SIMISA@@@@@@@@@@JINX0s1t"
CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "ORZIPGui"
CONFIG_FILE = CONFIG_DIR / "settings.ini"


@dataclass(frozen=True)
class ThemePalette:
    app_bg: str
    header_bg: str
    panel_bg: str
    input_bg: str
    log_bg: str
    log_fg: str
    text_fg: str
    help_fg: str
    muted_fg: str
    accent_fg: str
    accent_border: str
    warning_bg: str
    danger_bg: str
    button_bg: str
    primary_button_bg: str
    border: str
    disabled_bg: str
    disabled_fg: str
    ready_bg: str
    busy_bg: str
    tree_selected_bg: str
    tree_selected_fg: str


THEMES: dict[str, ThemePalette] = {
    "Light": ThemePalette(
        app_bg="#f4f2ed",
        header_bg="#eee9e1",
        panel_bg="#f8f7f3",
        input_bg="#ffffff",
        log_bg="#202020",
        log_fg="#f4f4f4",
        text_fg="#2e2e2e",
        help_fg="#555555",
        muted_fg="#7b6b5c",
        accent_fg="#7a4634",
        accent_border="#8b6f5b",
        warning_bg="#fff0c7",
        danger_bg="#f0d6d6",
        button_bg="#dcefe2",
        primary_button_bg="#cfe3d6",
        border="#8b6f5b",
        disabled_bg="#e3e3e3",
        disabled_fg="#777777",
        ready_bg="#fff0c7",
        busy_bg="#d9edf7",
        tree_selected_bg="#cfe3d6",
        tree_selected_fg="#000000",
    ),
    "Dark": ThemePalette(
        app_bg="#2D2D2D",
        header_bg="#262626",
        panel_bg="#222222",
        input_bg="#1B1B1B",
        log_bg="#181818",
        log_fg="#F0F0F0",
        text_fg="#F0F0F0",
        help_fg="#CDCDCD",
        muted_fg="#B8B8B8",
        accent_fg="#E2B27E",
        accent_border="#CD8434",
        warning_bg="#EBAA51",
        danger_bg="#D65C4B",
        button_bg="#343434",
        primary_button_bg="#3A3A3A",
        border="#5C5C5C",
        disabled_bg="#2B2B2B",
        disabled_fg="#707070",
        ready_bg="#EBAA51",
        busy_bg="#3A3A3A",
        tree_selected_bg="#CD8434",
        tree_selected_fg="#181818",
    ),
}

# Backward-compatible names used during initial widget construction.
BG = THEMES["Light"].app_bg
PANEL = THEMES["Light"].panel_bg
BORDER = THEMES["Light"].border
GREEN = THEMES["Light"].button_bg
GREEN_DARK = THEMES["Light"].accent_border
READY = THEMES["Light"].ready_bg
DISABLED = THEMES["Light"].disabled_bg
LOG_BG = THEMES["Light"].log_bg
LOG_FG = THEMES["Light"].log_fg
ACCENT = THEMES["Light"].accent_fg


@dataclass
class ShapeRecord:
    path: Path
    folder: str
    size_kb: int
    status: str


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def bundled_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", app_dir())).resolve()


def app_icon_path() -> Path:
    for base in (bundled_dir(), app_dir()):
        for relative in (
            Path("assets") / "OpenRailsShapePacker_RSS.ico",
            Path("assets") / "SFM3.ico",
        ):
            candidate = base / relative
            if candidate.exists():
                return candidate
    return app_dir() / "assets" / "OpenRailsShapePacker_RSS.ico"


def banner_image_path() -> Path:
    for base in (bundled_dir(), app_dir()):
        candidate = base / "assets" / "OpenRailsShapePacker_RSS.png"
        if candidate.exists():
            return candidate
    return app_dir() / "assets" / "OpenRailsShapePacker_RSS.png"


def is_uncompressed_shape(path: Path) -> bool:
    try:
        data = path.read_bytes()[:64]
    except OSError:
        return False
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        try:
            return data.decode("utf-16", errors="ignore")[:24] == UNCOMPRESSED_MAGIC
        except UnicodeError:
            return False
    try:
        return data.decode("ascii", errors="ignore")[:24] == UNCOMPRESSED_MAGIC
    except Exception:
        return False


def is_compressed_shape(path: Path) -> bool:
    try:
        data = path.read_bytes()[:32]
    except OSError:
        return False
    if is_uncompressed_shape(path):
        return False
    if len(data) >= 2 and int.from_bytes(data[:2], "little") in (18771, 21321):
        return True
    return path.suffix.lower() == ".s"


def shape_status(path: Path) -> str:
    if is_uncompressed_shape(path):
        return "Uncompressed"
    if is_compressed_shape(path):
        return "Compressed"
    return "Unknown"


def line_has_orzip_warning(line: str) -> bool:
    return "warning:" in line.lower()


def default_orzip_cmd() -> str:
    for folder in (app_dir(), bundled_dir()):
        for name in ("orzip.exe", "orzip"):
            candidate = folder / name
            if candidate.exists():
                return str(candidate)
    return shutil.which("orzip.exe") or shutil.which("orzip") or str(app_dir() / "orzip.exe")


class ORZipGui:
    def __init__(self, root: Tk) -> None:
        self.root = root
        root.title(f"{APP_NAME} {APP_VERSION}")
        self.apply_default_window_size()
        root.configure(bg=BG)
        try:
            root.iconbitmap(default=str(app_icon_path()))
        except Exception:
            pass

        self.config = self.load_config()
        start_dir = self.config.get("settings", "route_path", fallback=os.getcwd())
        self.route_path = StringVar(value=start_dir if Path(start_dir).exists() else os.getcwd())
        self.orzip_cmd = StringVar(value=self.resolve_orzip_cmd(self.config.get("settings", "orzip_cmd", fallback="")))
        self.operation = StringVar(value=self.config.get("settings", "operation", fallback="auto"))
        self.selection_mode = StringVar(value=self.config.get("settings", "selection", fallback="selected"))
        self.search_filter = StringVar(value="")
        self.include_subfolders = BooleanVar(value=self.config.getboolean("settings", "include_subfolders", fallback=True))
        self.make_backups = BooleanVar(value=self.config.getboolean("settings", "make_backups", fallback=True))
        self.skip_unchanged = BooleanVar(value=self.config.getboolean("settings", "skip_unchanged", fallback=True))
        self.force_overwrite = BooleanVar(value=self.config.getboolean("settings", "force_overwrite", fallback=False))
        self.verify_detect = BooleanVar(value=self.config.getboolean("settings", "verify_detect", fallback=True))
        saved_theme = self.config.get("settings", "theme", fallback="Light")
        self.theme_name = StringVar(value=saved_theme if saved_theme in THEMES else "Light")
        self.confirm_run = BooleanVar(value=self.config.getboolean("settings", "confirm_run", fallback=True))
        self.records: list[ShapeRecord] = []
        self.item_paths: dict[str, Path] = {}
        self.last_run_warnings = 0
        self.abort_requested = False
        self.worker: threading.Thread | None = None

        self.configure_style()
        self.build_ui()
        self.apply_theme()
        self.scan()

    def apply_default_window_size(self) -> None:
        """Choose a startup size that exposes Run buttons and log header."""
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(1040, max(900, screen_w - 80))
        # 960 shows the ORZIP Program/READY block plus the fixed action
        # buttons and top of the log on normal desktop displays. Clamp for
        # smaller screens so the window still fits and scrolling remains usable.
        height = min(960, max(760, screen_h - 60))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 3)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(860, 700)

    def palette(self) -> ThemePalette:
        return THEMES.get(self.theme_name.get(), THEMES["Light"])

    def configure_style(self) -> None:
        colors = self.palette()
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "Treeview",
            background=colors.input_bg,
            fieldbackground=colors.input_bg,
            foreground=colors.text_fg,
            rowheight=22,
            font=("Segoe UI", 9),
            bordercolor=colors.border,
            lightcolor=colors.border,
            darkcolor=colors.border,
        )
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background=colors.header_bg,
            foreground=colors.text_fg,
            bordercolor=colors.border,
        )
        style.configure("TScrollbar", background=colors.button_bg, troughcolor=colors.app_bg, bordercolor=colors.border, arrowcolor=colors.text_fg)
        style.configure("TMenubutton", background=colors.button_bg, foreground=colors.text_fg, bordercolor=colors.border)
        style.map(
            "Treeview",
            background=[("selected", colors.tree_selected_bg)],
            foreground=[("selected", colors.tree_selected_fg)],
        )

    def apply_theme(self) -> None:
        colors = self.palette()
        self.root.configure(bg=colors.app_bg)
        self.configure_style()
        self.apply_theme_to_widget(self.root, colors)
        if hasattr(self, "ready_label"):
            self.set_ready(self.ready_label.cget("text"), busy=self.ready_label.cget("text") in {"RUNNING", "SCANNING", "ABORTING"})

    def apply_theme_to_widget(self, widget, colors: ThemePalette) -> None:
        cls = widget.winfo_class()
        parent_bg = colors.app_bg
        try:
            parent = widget.master
            if parent is not None and parent.winfo_class() not in {"Tk", "Toplevel"}:
                parent_bg = parent.cget("bg")
        except Exception:
            pass

        try:
            if cls == "Canvas":
                widget.configure(bg=colors.app_bg, highlightbackground=colors.border)
            elif cls == "Frame":
                current = widget.cget("bg")
                role_bg = colors.panel_bg if current.lower() in {PANEL.lower(), "#222222"} else colors.app_bg
                widget.configure(bg=role_bg, highlightbackground=colors.border)
            elif cls == "Labelframe":
                widget.configure(bg=colors.panel_bg, fg=colors.accent_fg, highlightbackground=colors.border)
            elif cls == "Label":
                current_fg = str(widget.cget("fg")).lower()
                fg = colors.accent_fg if current_fg in {ACCENT.lower(), "#c0925b", "#7b4f3f"} else colors.muted_fg if current_fg in {"#666", "#555", "#7b6b5c"} else colors.text_fg
                widget.configure(bg=parent_bg, fg=fg)
            elif cls in {"Button", "Menubutton"}:
                label = str(widget.cget("text"))
                bg = colors.primary_button_bg if label in {"Run ORZIP", "Scan"} else colors.button_bg
                if str(widget.cget("state")) == "disabled":
                    bg = colors.disabled_bg
                widget.configure(bg=bg, fg=colors.text_fg, activebackground=colors.accent_border, activeforeground=colors.tree_selected_fg, disabledforeground=colors.disabled_fg, highlightbackground=colors.border)
            elif cls in {"Checkbutton", "Radiobutton"}:
                widget.configure(bg=parent_bg, fg=colors.text_fg, activebackground=parent_bg, activeforeground=colors.accent_fg, selectcolor=colors.input_bg, highlightbackground=colors.border)
            elif cls == "Entry":
                widget.configure(bg=colors.input_bg, fg=colors.text_fg, insertbackground=colors.text_fg, disabledbackground=colors.disabled_bg, disabledforeground=colors.disabled_fg, highlightbackground=colors.border)
            elif cls == "Text":
                widget.configure(bg=colors.log_bg, fg=colors.log_fg, insertbackground=colors.log_fg)
            elif cls == "Toplevel":
                widget.configure(bg=colors.app_bg)
        except Exception:
            pass
        for child in widget.winfo_children():
            self.apply_theme_to_widget(child, colors)

    def change_theme(self, *_args) -> None:
        self.save_config()
        self.apply_theme()

    def load_config(self) -> configparser.ConfigParser:
        cp = configparser.ConfigParser()
        if CONFIG_FILE.exists():
            cp.read(CONFIG_FILE)
        if not cp.has_section("settings"):
            cp.add_section("settings")
        return cp

    def save_config(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.config.set("settings", "route_path", self.route_path.get())
        self.config.set("settings", "orzip_cmd", self.orzip_cmd.get())
        self.config.set("settings", "operation", self.operation.get())
        self.config.set("settings", "selection", self.selection_mode.get())
        self.config.set("settings", "include_subfolders", str(self.include_subfolders.get()))
        self.config.set("settings", "make_backups", str(self.make_backups.get()))
        self.config.set("settings", "skip_unchanged", str(self.skip_unchanged.get()))
        self.config.set("settings", "force_overwrite", str(self.force_overwrite.get()))
        self.config.set("settings", "verify_detect", str(self.verify_detect.get()))
        self.config.set("settings", "confirm_run", str(self.confirm_run.get()))
        self.config.set("settings", "theme", self.theme_name.get())
        with CONFIG_FILE.open("w", encoding="utf-8") as f:
            self.config.write(f)

    def resolve_orzip_cmd(self, configured: str) -> str:
        cmd = configured.strip()
        if not cmd:
            return default_orzip_cmd()
        if Path(cmd).exists() or shutil.which(cmd):
            return cmd
        return default_orzip_cmd()

    def build_ui(self) -> None:
        outer = Frame(self.root, bg=BG)
        outer.pack(fill=BOTH, expand=True)
        self.main_canvas = Canvas(outer, bg=BG, highlightthickness=0)
        self.main_scrollbar = ttk.Scrollbar(outer, orient=VERTICAL, command=self.main_canvas.yview)
        self.main_canvas.configure(yscrollcommand=self.main_scrollbar.set)
        self.main_scrollbar.pack(side=RIGHT, fill=Y)
        self.main_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self.content = Frame(self.main_canvas, bg=BG)
        self.content_window = self.main_canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", self.update_main_scroll_region)
        self.main_canvas.bind("<Configure>", self.resize_content_width)
        self.root.bind_all("<MouseWheel>", self.on_mousewheel)

        self.build_banner()
        self.build_path_row()

        main = Frame(self.content, bg=BG)
        main.pack(fill=BOTH, expand=True, padx=14, pady=(4, 8))

        left = Frame(main, bg=BG)
        left.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 6))
        right = Frame(main, bg=BG)
        right.pack(side=RIGHT, fill=BOTH, expand=True, padx=(6, 0))

        self.build_operation_panel(left)
        self.build_selection_panel(left)
        self.build_file_list(left)
        self.build_options_panel(right)
        self.build_status_panel(right)
        self.build_settings_panel(right)
        self.build_footer()
        self.build_log()
        self.build_buttons()

    def update_main_scroll_region(self, _event=None) -> None:
        self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

    def resize_content_width(self, event) -> None:
        self.main_canvas.itemconfigure(self.content_window, width=event.width)

    def on_mousewheel(self, event) -> None:
        self.main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def build_banner(self) -> None:
        banner = Frame(self.content, bg="#eee9e1", highlightbackground=BORDER, highlightthickness=1)
        banner.pack(fill=X, padx=14, pady=(10, 8), ipady=8)
        logo_path = banner_image_path()
        try:
            self.banner_image = PhotoImage(file=str(logo_path)).subsample(4, 4)
            logo = Label(banner, image=self.banner_image, bg="#eee9e1")
        except Exception:
            self.banner_image = None
            logo = Label(banner, text="RSS", bg="#3b2a2a", fg="#c0925b", font=("Segoe UI", 18, "bold"), width=5)
        logo.pack(side=LEFT, padx=(18, 10), pady=6)
        title = Frame(banner, bg="#eee9e1")
        title.pack(side=LEFT, fill=X, expand=True)
        Label(title, text=APP_NAME, bg="#eee9e1", fg="#2e2e2e", font=("Segoe UI", 26, "bold")).pack(anchor="w")
        Label(title, text="COMPRESS AND UNCOMPRESS SHAPE FILES", bg="#eee9e1", fg=ACCENT, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        Label(banner, text=f"v{APP_VERSION}", bg="#efefef", fg="#555", relief="groove", padx=8, pady=3).pack(side=RIGHT, padx=14)

    def build_path_row(self) -> None:
        row = Frame(self.content, bg=BG)
        row.pack(fill=X, padx=18, pady=(0, 6))
        Label(row, text="Shape Path:", bg=BG).pack(side=LEFT)
        Entry(row, textvariable=self.route_path).pack(side=LEFT, fill=X, expand=True, padx=(8, 8))
        Button(row, text="Recent ▾", bg=GREEN, command=self.show_recent_menu).pack(side=LEFT, padx=(0, 8))
        Button(row, text="Browse...", command=self.browse_folder).pack(side=LEFT)

    def panel(self, parent: Frame, title: str) -> LabelFrame:
        lf = LabelFrame(parent, text=title, bg=PANEL, fg="#7b4f3f", padx=8, pady=8)
        lf.pack(fill=BOTH, expand=False, pady=(0, 10))
        return lf

    def build_operation_panel(self, parent: Frame) -> None:
        lf = self.panel(parent, "Mode")
        for text, value in [("Auto-detect needed action", "auto"), ("Compress uncompressed shapes", "compress"), ("Uncompress compressed shapes", "uncompress"), ("Detect file type / verify compressed files", "detect"), ("Validate shape files", "validate")]:
            Radiobutton(lf, text=text, value=value, variable=self.operation, bg=PANEL, anchor="w").pack(fill=X, anchor="w", pady=1)

    def build_selection_panel(self, parent: Frame) -> None:
        lf = self.panel(parent, "Selection")
        top = Frame(lf, bg=PANEL)
        top.pack(fill=X)
        radio_col = Frame(top, bg=PANEL)
        radio_col.pack(side=LEFT, fill=X, expand=True)
        for text, value in [("Use selected files", "selected"), ("Use all scanned files", "all"), ("Use current folder only", "folder")]:
            Radiobutton(radio_col, text=text, value=value, variable=self.selection_mode, bg=PANEL, anchor="w").pack(fill=X, anchor="w", pady=1)
        pick_col = Frame(top, bg=PANEL)
        pick_col.pack(side=RIGHT, fill=Y, padx=(10, 0))
        Button(pick_col, text="Select Uncompressed", width=19, command=lambda: self.select_by_status("Uncompressed")).pack(fill=X, pady=(0, 3))
        Button(pick_col, text="Select Compressed", width=19, command=lambda: self.select_by_status("Compressed")).pack(fill=X, pady=(0, 3))
        Button(pick_col, text="Clear Selection", width=19, command=self.clear_file_selection).pack(fill=X)
        row = Frame(lf, bg=PANEL)
        row.pack(fill=X, pady=(8, 0))
        Label(row, text="Search:", bg=PANEL).pack(side=LEFT)
        Entry(row, textvariable=self.search_filter, width=28).pack(side=LEFT, fill=X, expand=True, padx=(5, 5))
        Button(row, text="Clear", command=lambda: self.search_filter.set("")).pack(side=LEFT)
        Checkbutton(lf, text="Include subfolders while scanning", variable=self.include_subfolders, bg=PANEL).pack(anchor="w", pady=(6, 0))

    def build_file_list(self, parent: Frame) -> None:
        lf = self.panel(parent, "Shape Files")
        lf.pack(fill=BOTH, expand=True, pady=(0, 10))
        cols = ("name", "folder", "size", "status")
        tree_frame = Frame(lf, bg=PANEL)
        tree_frame.pack(fill=BOTH, expand=True)
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="extended")
        self.tree_scroll = ttk.Scrollbar(tree_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.tree_scroll.set)
        for col, title, width in [("name", "File", 230), ("folder", "Folder", 170), ("size", "Size", 70), ("status", "Status", 105)]:
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor="w")
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        self.tree_scroll.pack(side=RIGHT, fill=Y)

    def build_options_panel(self, parent: Frame) -> None:
        lf = self.panel(parent, "Options")
        Checkbutton(lf, text="Create .PreORZIP backup before changing files", variable=self.make_backups, bg=PANEL).grid(row=0, column=0, sticky="w", pady=2)
        Checkbutton(lf, text="Skip files that already match the selected mode", variable=self.skip_unchanged, bg=PANEL).grid(row=1, column=0, sticky="w", pady=2)
        Checkbutton(lf, text="Overwrite existing ORZIP outputs (--force)", variable=self.force_overwrite, bg=PANEL).grid(row=2, column=0, sticky="w", pady=2)
        Checkbutton(lf, text="Verify compressed files during Detect", variable=self.verify_detect, bg=PANEL).grid(row=3, column=0, sticky="w", pady=2)
        Checkbutton(lf, text="Confirm before Run", variable=self.confirm_run, bg=PANEL).grid(row=4, column=0, sticky="w", pady=2)
        theme_row = Frame(lf, bg=PANEL)
        theme_row.grid(row=5, column=0, sticky="w", pady=(8, 0))
        Label(theme_row, text="Theme:", bg=PANEL).pack(side=LEFT)
        self.theme_menu = ttk.OptionMenu(theme_row, self.theme_name, self.theme_name.get(), *THEMES.keys(), command=self.change_theme)
        self.theme_menu.pack(side=LEFT, padx=(6, 0))

    def build_status_panel(self, parent: Frame) -> None:
        lf = self.panel(parent, "Status")
        grid = Frame(lf, bg=PANEL)
        grid.pack(fill=BOTH, expand=True)
        headers = ["", "Files", "To Run"]
        for c, h in enumerate(headers):
            Label(grid, text=h, bg=PANEL, font=("Segoe UI", 9, "bold")).grid(row=0, column=c, sticky="e", padx=8)
        self.status_vars = {}
        for r, key in enumerate(["Total", "Compressed", "Uncompressed", "Unknown", "Selected", "Ready", "Warnings"], start=1):
            Label(grid, text=key, bg=PANEL).grid(row=r, column=0, sticky="w", padx=8, pady=2)
            a = StringVar(value="0")
            b = StringVar(value="0")
            self.status_vars[(key, "files")] = a
            self.status_vars[(key, "run")] = b
            Label(grid, textvariable=a, bg=PANEL).grid(row=r, column=1, sticky="e", padx=8)
            Label(grid, textvariable=b, bg=PANEL).grid(row=r, column=2, sticky="e", padx=8)

    def build_settings_panel(self, parent: Frame) -> None:
        lf = self.panel(parent, "ORZIP")
        Label(lf, text="Program:", bg=PANEL).grid(row=0, column=0, sticky="w")
        Entry(lf, textvariable=self.orzip_cmd, width=42).grid(row=0, column=1, sticky="ew", padx=(5, 5))
        Button(lf, text="Browse...", command=self.browse_orzip).grid(row=0, column=2)
        self.ready_label = Label(lf, text="READY", bg=READY, relief="groove", width=28, pady=4)
        self.ready_label.grid(row=1, column=1, sticky="ew", padx=(5, 5), pady=(8, 0))
        lf.columnconfigure(1, weight=1)

    def build_buttons(self) -> None:
        row = Frame(self.root, bg=BG)
        row.pack(side=BOTTOM, fill=X, padx=18, pady=(0, 8))
        Button(row, text="Scan", bg=GREEN, width=10, command=self.scan).pack(side=LEFT, padx=(0, 8))
        self.run_button = Button(row, text="Run ORZIP", bg=GREEN, width=12, command=self.run)
        self.run_button.pack(side=LEFT, padx=(0, 8))
        self.abort_button = Button(row, text="Abort", bg=DISABLED, width=10, state="disabled", command=self.abort)
        self.abort_button.pack(side=LEFT, padx=(0, 8))
        Button(row, text="Exit", bg=GREEN, width=10, command=self.root.destroy).pack(side=LEFT, padx=(0, 8))
        Button(row, text="Help", bg=GREEN, width=10, command=self.show_help).pack(side=RIGHT, padx=(8, 0))

    def build_log(self) -> None:
        log_panel = LabelFrame(self.root, text="ORZIP Output Log", bg=BG, fg="#7b4f3f", padx=6, pady=6)
        log_panel.pack(side=BOTTOM, fill=X, expand=False, padx=18, pady=(0, 6))
        log_buttons = Frame(log_panel, bg=BG)
        log_buttons.pack(fill=X, pady=(0, 4))
        Label(log_buttons, text="ORZIP stdout/stderr appears here while the tool runs.", bg=BG, fg="#666").pack(side=LEFT)
        Button(log_buttons, text="Clear Log", command=self.clear_log).pack(side=RIGHT, padx=(6, 0))
        Button(log_buttons, text="Copy Log", command=self.copy_log).pack(side=RIGHT)
        self.log = ScrolledText(log_panel, bg=LOG_BG, fg=LOG_FG, insertbackground=LOG_FG, height=12, wrap="word")
        self.log.pack(fill=BOTH, expand=True)
        self.log.insert(END, "Open Rails Shape Packer ready. Choose a folder, scan, select files, then click Run ORZIP.\n")
        self.log.config(state="disabled")

    def build_footer(self) -> None:
        row = Frame(self.root, bg=BG)
        row.pack(side=BOTTOM, fill=X, padx=18, pady=(0, 8))
        Label(row, text="License: follows bundled ORZIP/Open Rails tool licensing", bg=BG, fg="#7b6b5c").pack(side=LEFT)
        Label(row, text="Open Rails shape compression front-end", bg=BG, fg="#7b6b5c").pack(side=RIGHT)

    def log_line(self, text: str) -> None:
        self.log.config(state="normal")
        self.log.insert(END, text.rstrip() + "\n")
        self.log.see(END)
        self.log.config(state="disabled")

    def clear_log(self) -> None:
        self.log.config(state="normal")
        self.log.delete("1.0", END)
        self.log.config(state="disabled")

    def copy_log(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(self.log.get("1.0", END).rstrip())
        self.log_line("[Shape Packer] Log copied to clipboard.")

    def log_command(self, cmd: list[str], cwd: Path) -> None:
        self.log_line("-" * 72)
        self.log_line(f"[Shape Packer] Working folder: {cwd}")
        self.log_line(f"[Shape Packer] Command: {subprocess.list2cmdline(cmd)}")
        self.log_line("[ORZIP output begins]")

    def set_ready(self, text: str, busy: bool = False, abort_enabled: bool = False) -> None:
        colors = self.palette()
        self.ready_label.config(text=text, bg=(colors.busy_bg if busy else colors.ready_bg), fg=colors.text_fg)
        self.run_button.config(state=("disabled" if busy else "normal"), bg=(colors.disabled_bg if busy else colors.primary_button_bg))
        self.abort_button.config(
            state=("normal" if abort_enabled else "disabled"),
            bg=(colors.danger_bg if abort_enabled else colors.disabled_bg),
            fg=colors.text_fg if abort_enabled else colors.disabled_fg,
        )

    def browse_folder(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.route_path.get() or os.getcwd(), title="Select shape-file folder")
        if folder:
            self.route_path.set(folder)
            self.save_recent(folder)
            self.scan()

    def browse_orzip(self) -> None:
        filetypes = [("ORZIP", "orzip.exe"), ("Executable", "*.exe"), ("All files", "*")]
        path = filedialog.askopenfilename(initialdir=str(app_dir()), title="Select orzip.exe", filetypes=filetypes)
        if path:
            self.orzip_cmd.set(path)
            self.save_config()

    def save_recent(self, path: str) -> None:
        old = [p for p in self.config.get("settings", "recent", fallback="").split("|") if p and p != path]
        recent = [path, *old][:8]
        self.config.set("settings", "recent", "|".join(recent))
        self.save_config()

    def show_recent_menu(self) -> None:
        menu = Menu(self.root, tearoff=0)
        recent = [p for p in self.config.get("settings", "recent", fallback="").split("|") if p]
        if not recent:
            menu.add_command(label="No recent folders", state="disabled")
        for path in recent:
            menu.add_command(label=path, command=lambda p=path: self.select_recent(p))
        x = self.root.winfo_pointerx(); y = self.root.winfo_pointery()
        menu.tk_popup(x, y)

    def select_recent(self, path: str) -> None:
        self.route_path.set(path)
        self.scan()

    def scan(self) -> None:
        root = Path(self.route_path.get()).expanduser()
        self.set_ready("SCANNING", busy=True)
        self.root.update_idletasks()
        self.records.clear()
        self.item_paths.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        if not root.exists() or not root.is_dir():
            self.log_line(f"Folder not found: {root}")
            self.update_status()
            self.set_ready("NO FOLDER")
            return
        self.save_recent(str(root))
        pattern = "**/*.s" if self.include_subfolders.get() else "*.s"
        query = self.search_filter.get().strip().lower()
        try:
            paths = sorted(root.glob(pattern), key=lambda p: str(p.relative_to(root)).upper())
        except OSError as e:
            self.log_line(f"Scan failed: {e}")
            self.set_ready("SCAN ERROR")
            return
        for path in paths:
            if query and query not in path.name.lower():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            folder = "." if path.parent == root else str(path.parent.relative_to(root))
            rec = ShapeRecord(path=path, folder=folder, size_kb=max(1, stat.st_size // 1024), status=shape_status(path))
            self.records.append(rec)
            item = self.tree.insert("", END, values=(path.name, rec.folder, f"{rec.size_kb} Kb", rec.status))
            self.item_paths[item] = path
            if len(self.records) % 100 == 0:
                self.ready_label.config(text=f"SCANNING {len(self.records)}")
                self.root.update_idletasks()
        self.update_status()
        self.set_ready("READY")
        self.log_line(f"Scan complete: {len(self.records)} .S file(s) found in {root}")

    def selected_records(self) -> list[ShapeRecord]:
        root = Path(self.route_path.get()).expanduser()
        if self.selection_mode.get() == "all":
            return list(self.records)
        if self.selection_mode.get() == "folder":
            return [r for r in self.records if r.path.parent == root]
        selected = set(self.item_paths[item] for item in self.tree.selection() if item in self.item_paths)
        return [r for r in self.records if r.path in selected]

    def select_by_status(self, status: str) -> None:
        matches = [item for item, path in self.item_paths.items() if shape_status(path) == status]
        self.tree.selection_set(matches)
        if matches:
            self.tree.focus(matches[0])
            self.tree.see(matches[0])
        self.selection_mode.set("selected")
        self.update_status()
        self.log_line(f"Selected {len(matches)} {status.lower()} shape file(s).")

    def clear_file_selection(self) -> None:
        self.tree.selection_remove(self.tree.selection())
        self.selection_mode.set("selected")
        self.update_status()
        self.log_line("Cleared shape-file selection.")

    def operation_for(self, rec: ShapeRecord) -> str | None:
        mode = self.operation.get()
        if mode in {"detect", "validate"}:
            return mode
        if mode == "compress":
            if self.skip_unchanged.get() and rec.status == "Compressed":
                return None
            return "compress"
        if mode == "uncompress":
            if self.skip_unchanged.get() and rec.status == "Uncompressed":
                return None
            return "uncompress"
        if rec.status == "Compressed":
            return "uncompress"
        if rec.status == "Uncompressed":
            return "compress"
        return None

    def ready_records(self) -> list[tuple[ShapeRecord, str]]:
        return [(rec, op) for rec in self.selected_records() if (op := self.operation_for(rec))]

    def update_status(self) -> None:
        selected = self.selected_records()
        ready = self.ready_records()
        counts = {
            "Total": len(self.records),
            "Compressed": sum(1 for r in self.records if r.status == "Compressed"),
            "Uncompressed": sum(1 for r in self.records if r.status == "Uncompressed"),
            "Unknown": sum(1 for r in self.records if r.status == "Unknown"),
            "Selected": len(selected),
            "Ready": len(ready),
            "Warnings": self.last_run_warnings,
        }
        run_counts = {
            "Total": len(ready),
            "Compressed": sum(1 for r, _ in ready if r.status == "Compressed"),
            "Uncompressed": sum(1 for r, _ in ready if r.status == "Uncompressed"),
            "Unknown": sum(1 for r, _ in ready if r.status == "Unknown"),
            "Selected": len(ready),
            "Ready": len(ready),
            "Warnings": 0,
        }
        for key, value in counts.items():
            self.status_vars[(key, "files")].set(str(value))
            self.status_vars[(key, "run")].set(str(run_counts[key]))

    def orzip_available(self) -> bool:
        cmd = self.orzip_cmd.get().strip()
        return bool(cmd and (Path(cmd).exists() or shutil.which(cmd)))

    def backup_file(self, path: Path) -> Path | None:
        backup = Path(str(path) + ".PreORZIP")
        if not backup.exists():
            shutil.copy2(path, backup)
            return backup
        return None

    def run(self) -> None:
        self.save_config()
        self.update_status()
        jobs = self.ready_records()
        if not jobs:
            messagebox.showinfo("Nothing to run", "No files are ready for the selected ORZIP operation.")
            return
        if not self.orzip_available():
            messagebox.showerror("ORZIP not found", f"Unable to find {self.orzip_cmd.get()} on PATH or at the configured path.")
            return
        if self.confirm_run.get() and not messagebox.askyesno("Confirm ORZIP run", f"Run ORZIP on {len(jobs)} file(s)?"):
            return
        self.abort_requested = False
        self.last_run_warnings = 0
        self.update_status()
        self.clear_log()
        self.log_line(f"[Shape Packer] Starting ORZIP run for {len(jobs)} file(s).")
        self.worker = threading.Thread(target=self.run_worker, args=(jobs,), daemon=True)
        self.set_ready("RUNNING", busy=True, abort_enabled=True)
        self.worker.start()

    def build_orzip_command(self, rec: ShapeRecord, op: str) -> list[str]:
        cmd = [self.orzip_cmd.get(), op]
        if op == "detect" and self.verify_detect.get():
            cmd.append("--verify")
        if op in {"compress", "uncompress"} and self.force_overwrite.get():
            cmd.append("--force")
        if op == "compress":
            cmd.extend(["--level", "9"])
        cmd.append(str(rec.path))
        return cmd

    def run_worker(self, jobs: list[tuple[ShapeRecord, str]]) -> None:
        ok = warn = fail = skip = 0
        for rec, op in jobs:
            if self.abort_requested:
                skip += 1
                self.root.after(0, self.log_line, "Abort requested; stopping after current file.")
                break
            try:
                if self.make_backups.get() and op in {"compress", "uncompress"}:
                    backup = self.backup_file(rec.path)
                    if backup is not None:
                        self.root.after(0, self.log_line, f"Backup: {backup.name}")
                cmd = self.build_orzip_command(rec, op)
                cwd = rec.path.parent
                self.root.after(0, self.log_command, cmd, cwd)
                creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(cwd),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    errors="replace",
                    creationflags=creationflags,
                )
                assert proc.stdout is not None
                file_had_warning = False
                for line in proc.stdout:
                    stripped = line.rstrip()
                    if line_has_orzip_warning(stripped):
                        file_had_warning = True
                    self.root.after(0, self.log_line, stripped)
                    if self.abort_requested and proc.poll() is None:
                        proc.terminate()
                return_code = proc.wait()
                self.root.after(0, self.log_line, f"[ORZIP exit code: {return_code}]")
                if return_code == 0:
                    if file_had_warning:
                        warn += 1
                    else:
                        ok += 1
                else:
                    fail += 1
                    self.root.after(0, self.log_line, f"FAILED ({return_code}): {rec.path.name}")
            except Exception as e:
                fail += 1
                self.root.after(0, self.log_line, f"FAILED: {rec.path.name}: {e}")
        self.root.after(0, self.finish_run, ok, warn, fail, skip)

    def finish_run(self, ok: int, warn: int, fail: int, skip: int) -> None:
        self.last_run_warnings = warn
        self.scan()
        self.set_ready("WARNINGS" if warn and not fail else "READY")
        self.update_status()
        self.log_line(f"Run complete: {ok} succeeded, {warn} warning(s), {fail} failed, {skip} skipped.")
        if fail:
            messagebox.showwarning("ORZIP complete with errors", f"{ok} succeeded, {warn} warning(s), {fail} failed, {skip} skipped. See log for details.")
        elif warn:
            messagebox.showwarning("ORZIP complete with warnings", f"{ok} succeeded, {warn} warning(s), {skip} skipped. See log for details.")
        else:
            messagebox.showinfo("ORZIP complete", f"{ok} succeeded, {skip} skipped.")

    def abort(self) -> None:
        self.abort_requested = True
        self.set_ready("ABORTING", busy=True, abort_enabled=True)

    def show_help(self) -> None:
        colors = self.palette()
        win = Toplevel(self.root)
        win.title(f"{APP_NAME} Help")
        win.configure(bg=colors.app_bg)
        text = ScrolledText(win, width=92, height=30, bg=colors.log_bg, fg=colors.log_fg, insertbackground=colors.log_fg)
        text.pack(fill=BOTH, expand=True, padx=8, pady=8)
        text.insert(END, f"""{APP_NAME} {APP_VERSION}\n\nThis is a focused front-end for ORZIP. It exposes the normal Open Rails shape-file compression workflow.\n\nWorkflow:\n  1. Browse to a folder containing Open Rails .S shape files.\n  2. Press Scan.\n  3. Select one or more files, or choose all/current-folder selection.\n  4. Choose Auto, Compress, Uncompress, Detect, or Validate.\n  5. Press Run ORZIP.\n\nModes:\n  Auto-detect: compressed files are uncompressed, uncompressed files are compressed.\n  Compress: runs ORZIP compress on suitable files.\n  Uncompress: runs ORZIP uncompress on suitable files.\n  Detect: reports file type; optional verify checks compressed payload size.\n  Validate: asks ORZIP to validate selected shape files.\n\nSafety:\n  Enable .PreORZIP backups when working on original assets. A backup is created beside each shape file before ORZIP changes it. Work on copies for valuable route or rolling-stock files.\n""")
        text.config(state="disabled")


def run_self_tests() -> int:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        uncompressed = root / "plain.s"
        uncompressed.write_text("SIMISA@@@@@@@@@@JINX0s1t______\r\nshape ( x )\r\n", encoding="utf-16")
        compressed = root / "packed.s"
        compressed.write_bytes(b"SI" + b"\x00" * 16)
        other = root / "note.txt"
        other.write_text("ignore")
        assert is_uncompressed_shape(uncompressed)
        assert shape_status(uncompressed) == "Uncompressed"
        assert shape_status(compressed) == "Compressed"
        assert not is_compressed_shape(other)
        assert default_orzip_cmd()
        assert THEMES["Dark"].app_bg == "#2D2D2D"
        assert THEMES["Dark"].accent_fg == "#E2B27E"
        assert THEMES["Light"].app_bg == "#f4f2ed"
        assert THEMES["Light"].log_bg == "#202020"
        assert THEMES["Light"].log_fg == "#f4f4f4"
        assert line_has_orzip_warning("  warning: trailing data after zlib stream: 2651 bytes")
        assert line_has_orzip_warning("WARNING: trailing data after zlib stream: 7 bytes")
        assert not line_has_orzip_warning("BRAN_7204_A.s: OK")
    print("orzip gui self-tests passed")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return run_self_tests()
    root = Tk()
    app = ORZipGui(root)
    app.tree.bind("<<TreeviewSelect>>", lambda _event: app.update_status())
    for var in (app.operation, app.selection_mode, app.search_filter):
        var.trace_add("write", lambda *_: app.update_status())
    app.include_subfolders.trace_add("write", lambda *_: app.scan())
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
