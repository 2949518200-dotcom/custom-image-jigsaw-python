from __future__ import annotations

import argparse
import ctypes
import math
import random
import sys
import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from PIL import Image, ImageDraw, ImageOps, ImageTk


APP_TITLE = "【自定义图片拼图游戏】"
APP_VERSION = "1.0.0"
RESAMPLE = getattr(Image, "Resampling", Image).LANCZOS

COLORS = {
    "bg": "#101419",
    "surface": "#171d24",
    "surface_strong": "#202832",
    "line": "#303a46",
    "text": "#f5f2e9",
    "muted": "#9aa7b5",
    "accent": "#ff7043",
    "accent_hover": "#ff946f",
    "teal": "#33c6b5",
    "gold": "#f3c74f",
    "success": "#55c98b",
    "canvas": "#0d1116",
}


def enable_windows_high_dpi() -> None:
    if sys.platform != "win32":
        return

    # PER_MONITOR_AWARE_V2 keeps Tkinter crisp on scaled Windows displays.
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass

    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


@dataclass
class Piece:
    piece_id: int
    row: int
    col: int
    slot_index: int
    x: float = 0.0
    y: float = 0.0
    snapped: bool = False
    magnet: bool = False
    image_item: int = 0
    outline_item: int = 0
    photo: Optional[ImageTk.PhotoImage] = None
    source_crop: Optional[Image.Image] = None


def clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def format_time(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    minutes, remainder = divmod(total_seconds, 60)
    return f"{minutes:02d}:{remainder:02d}"


def shuffle_slots(count: int) -> list[int]:
    slots = list(range(count))
    if count > 1:
        # Sattolo shuffle guarantees that no piece starts in its correct position.
        for index in range(count - 1, 0, -1):
            swap_index = random.randrange(index)
            slots[index], slots[swap_index] = slots[swap_index], slots[index]
    return slots


def create_default_artwork(width: int = 1200, height: int = 800) -> Image.Image:
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)

    top = (18, 38, 63)
    middle = (54, 83, 106)
    bottom = (224, 161, 90)
    for y in range(height):
        if y < height * 0.55:
            ratio = y / max(1, int(height * 0.55))
            color = tuple(
                round(top[channel] + (middle[channel] - top[channel]) * ratio)
                for channel in range(3)
            )
        else:
            ratio = (y - height * 0.55) / max(1, height * 0.45)
            color = tuple(
                round(middle[channel] + (bottom[channel] - middle[channel]) * ratio)
                for channel in range(3)
            )
        draw.line((0, y, width, y), fill=color)

    draw.ellipse((748, 104, 952, 308), fill=(255, 241, 196))
    for x, y, radius in (
        (100, 98, 4),
        (186, 164, 3),
        (278, 82, 3),
        (392, 132, 4),
        (516, 70, 3),
        (1010, 92, 3),
        (1084, 154, 4),
        (934, 224, 3),
    ):
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=(255, 255, 255),
        )

    draw.polygon(
        [(0, 518), (174, 332), (322, 472), (488, 286), (742, 540), (0, 540)],
        fill=(39, 56, 74),
    )
    draw.polygon(
        [
            (312, 560),
            (570, 306),
            (754, 476),
            (930, 270),
            (1200, 560),
            (1200, 800),
            (312, 800),
        ],
        fill=(27, 44, 59),
    )
    draw.polygon(
        [(488, 508), (654, 508), (830, 800), (212, 800)],
        fill=(47, 196, 178),
    )
    draw.polygon(
        [(568, 508), (622, 508), (704, 800), (594, 800)],
        fill=(111, 218, 203),
    )

    draw.rectangle((80, 596, 302, 620), fill=(244, 196, 68))
    draw.rectangle((118, 620, 136, 800), fill=(244, 196, 68))
    draw.rectangle((246, 620, 264, 800), fill=(244, 196, 68))
    draw.polygon([(84, 598), (192, 516), (296, 598)], fill=(255, 112, 67))

    for index in range(15):
        x = 18 + index * 84
        y = 704 + (index % 3) * 28
        draw.polygon(
            [(x, y + 58), (x + 24, y), (x + 48, y + 58)],
            fill=(125, 207, 116),
        )

    grid_color = (63, 76, 90)
    for x in range(0, width + 1, 100):
        draw.line((x, 0, x, height), fill=grid_color, width=2)
    for y in range(0, height + 1, 100):
        draw.line((0, y, width, y), fill=grid_color, width=2)

    return image


class JigsawApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1280x860")
        self.root.minsize(900, 680)
        self.root.configure(bg=COLORS["bg"])
        self._apply_tk_scaling()

        self.original_image = create_default_artwork()
        self.display_image = self.original_image.copy()
        self.source_label = "内置示例图"
        self.size = 3
        self.pieces: list[Piece] = []
        self.board_width = 0.0
        self.board_height = 0.0
        self.cell_width = 0.0
        self.cell_height = 0.0
        self.board_left = 0.0
        self.board_top = 0.0
        self.moves = 0
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None
        self.completed = False
        self.hint_visible = False
        self.active_drag: Optional[dict[str, object]] = None
        self.hint_photo: Optional[ImageTk.PhotoImage] = None
        self.app_icon: Optional[ImageTk.PhotoImage] = None
        self.tick_after_id: Optional[str] = None
        self.hint_after_id: Optional[str] = None
        self.resize_after_id: Optional[str] = None
        self.completion_after_id: Optional[str] = None
        self.deal_after_id: Optional[str] = None
        self.drag_effect_after_id: Optional[str] = None
        self.drag_effects: dict[str, object] = {}
        self.piece_animation_after_ids: dict[int, str] = {}
        self.is_dealing = False
        self._last_canvas_size = (0, 0)

        self.size_var = tk.IntVar(value=self.size)
        self.progress_var = tk.StringVar(value="0 / 9")
        self.time_var = tk.StringVar(value="00:00")
        self.move_var = tk.StringVar(value="0")
        self.source_var = tk.StringVar(value=self.source_label)
        self.ready_var = tk.StringVar(value="内置图片已就绪")

        self._configure_styles()
        self._build_ui()
        self._set_window_icon()

        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.root.after(120, self.start_new_game)

    def _apply_tk_scaling(self) -> None:
        try:
            pixels_per_inch = self.root.winfo_fpixels("1i")
            self.root.tk.call("tk", "scaling", pixels_per_inch / 72)
        except tk.TclError:
            pass

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure(
            "TButton",
            background=COLORS["surface_strong"],
            foreground=COLORS["text"],
            bordercolor=COLORS["line"],
            lightcolor=COLORS["surface_strong"],
            darkcolor=COLORS["surface_strong"],
            focuscolor=COLORS["teal"],
            padding=(13, 8),
            relief="flat",
            font=("Microsoft YaHei UI", 10),
        )
        style.map(
            "TButton",
            background=[("active", "#26313d"), ("disabled", COLORS["surface"])],
            foreground=[("disabled", COLORS["muted"])],
            bordercolor=[("focus", COLORS["teal"])],
        )
        style.configure(
            "Accent.TButton",
            background=COLORS["accent"],
            foreground="#1a120e",
            bordercolor=COLORS["accent"],
            padding=(16, 9),
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        style.map(
            "Accent.TButton",
            background=[("active", COLORS["accent_hover"]), ("disabled", "#6e493d")],
            foreground=[("disabled", "#241a16")],
        )
        style.configure(
            "TCombobox",
            fieldbackground=COLORS["surface_strong"],
            background=COLORS["surface_strong"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["muted"],
            bordercolor=COLORS["line"],
            lightcolor=COLORS["line"],
            darkcolor=COLORS["line"],
            padding=(8, 6),
            font=("Microsoft YaHei UI", 10),
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", COLORS["surface_strong"])],
            foreground=[("readonly", COLORS["text"])],
            bordercolor=[("focus", COLORS["teal"])],
        )
        style.configure(
            "Jigsaw.Horizontal.TProgressbar",
            troughcolor="#0b0f13",
            background=COLORS["teal"],
            bordercolor="#0b0f13",
            lightcolor=COLORS["teal"],
            darkcolor=COLORS["teal"],
            thickness=7,
        )

        self.root.option_add("*TCombobox*Listbox.background", COLORS["surface_strong"])
        self.root.option_add("*TCombobox*Listbox.foreground", COLORS["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", COLORS["accent"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#1a120e")

    def _build_ui(self) -> None:
        header = tk.Frame(self.root, bg=COLORS["bg"], padx=22, pady=16)
        header.pack(fill="x")
        header.grid_columnconfigure(0, weight=1)

        title = tk.Label(
            header,
            text="自定义图片拼图游戏",
            bg=COLORS["bg"],
            fg=COLORS["text"],
            font=("Microsoft YaHei UI", 20, "bold"),
            anchor="w",
        )
        title.grid(row=0, column=0, sticky="w")

        subtitle = tk.Label(
            header,
            text="本地图片 · 随机拼图 · 自动吸附",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 9),
            anchor="w",
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(4, 0))

        ready = tk.Label(
            header,
            textvariable=self.ready_var,
            bg=COLORS["bg"],
            fg=COLORS["success"],
            font=("Microsoft YaHei UI", 9),
            anchor="e",
        )
        ready.grid(row=0, column=1, rowspan=2, sticky="e", padx=(20, 0))

        toolbar = tk.Frame(
            self.root,
            bg=COLORS["surface"],
            highlightbackground=COLORS["line"],
            highlightthickness=1,
            padx=22,
            pady=11,
        )
        toolbar.pack(fill="x")

        upload_button = ttk.Button(
            toolbar,
            text="选择本地图片",
            command=self.choose_image,
        )
        upload_button.pack(side="left")

        divider = tk.Frame(toolbar, bg=COLORS["line"], width=1, height=30)
        divider.pack(side="left", padx=12)

        size_label = tk.Label(
            toolbar,
            text="拼图尺寸",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 9),
        )
        size_label.pack(side="left", padx=(0, 7))

        self.size_combo = ttk.Combobox(
            toolbar,
            state="readonly",
            width=8,
            values=("3 × 3", "4 × 4", "5 × 5", "6 × 6"),
            textvariable=tk.StringVar(value="3 × 3"),
        )
        self.size_combo.pack(side="left")
        self.size_combo.bind("<<ComboboxSelected>>", self._on_size_changed)

        hint_button = ttk.Button(
            toolbar,
            text="提示原图",
            command=self.show_hint,
        )
        hint_button.pack(side="left", padx=(14, 0))

        reset_button = ttk.Button(
            toolbar,
            text="重置游戏",
            command=self.start_new_game,
        )
        reset_button.pack(side="left", padx=(8, 0))

        content = tk.Frame(self.root, bg=COLORS["bg"], padx=22, pady=18)
        content.pack(fill="both", expand=True)
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=0, minsize=236)

        board_frame = tk.Frame(
            content,
            bg=COLORS["canvas"],
            highlightbackground=COLORS["line"],
            highlightthickness=1,
        )
        board_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        board_frame.grid_rowconfigure(0, weight=1)
        board_frame.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            board_frame,
            bg=COLORS["canvas"],
            highlightthickness=0,
            bd=0,
            cursor="arrow",
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)

        sidebar = tk.Frame(content, bg=COLORS["bg"], width=236)
        sidebar.grid(row=0, column=1, sticky="nsew")
        sidebar.grid_propagate(False)

        self._build_sidebar(sidebar)

    def _build_sidebar(self, parent: tk.Frame) -> None:
        heading = tk.Label(
            parent,
            text="当前图片",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 9, "bold"),
            anchor="w",
        )
        heading.pack(fill="x", pady=(4, 6))

        source = tk.Label(
            parent,
            textvariable=self.source_var,
            bg=COLORS["bg"],
            fg=COLORS["text"],
            font=("Microsoft YaHei UI", 10),
            anchor="w",
            justify="left",
            wraplength=220,
        )
        source.pack(fill="x")

        tk.Frame(parent, bg=COLORS["line"], height=1).pack(fill="x", pady=(18, 10))

        self._create_stat_row(parent, "完成进度", self.progress_var)
        self.progress_bar = ttk.Progressbar(
            parent,
            style="Jigsaw.Horizontal.TProgressbar",
            orient="horizontal",
            mode="determinate",
            maximum=100,
        )
        self.progress_bar.pack(fill="x", pady=(0, 15))
        self._create_stat_row(parent, "已用时间", self.time_var)
        self._create_stat_row(parent, "拖动步数", self.move_var)

        tip = tk.Label(
            parent,
            text="将碎片拖到正确位置附近即可自动吸附。\n整张图片还原后会自动弹出通关结果。",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 9),
            justify="left",
            anchor="sw",
            wraplength=220,
        )
        tip.pack(side="bottom", fill="x", pady=(20, 4))

    def _create_stat_row(
        self,
        parent: tk.Frame,
        label_text: str,
        value_var: tk.StringVar,
    ) -> tk.Frame:
        row = tk.Frame(parent, bg=COLORS["bg"])
        row.pack(fill="x", pady=(0, 13))

        label = tk.Label(
            row,
            text=label_text,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 9),
            anchor="w",
        )
        label.pack(side="left")

        value = tk.Label(
            row,
            textvariable=value_var,
            bg=COLORS["bg"],
            fg=COLORS["text"],
            font=("Consolas", 13, "bold"),
            anchor="e",
        )
        value.pack(side="right")
        return row

    def _set_window_icon(self) -> None:
        icon_image = self.original_image.resize((64, 64), RESAMPLE)
        self.app_icon = ImageTk.PhotoImage(icon_image)
        self.root.iconphoto(True, self.app_icon)

    def _on_canvas_configure(self, event: tk.Event) -> None:
        new_size = (event.width, event.height)
        if new_size == self._last_canvas_size:
            return
        self._last_canvas_size = new_size

        if self.resize_after_id:
            self.root.after_cancel(self.resize_after_id)
        self.resize_after_id = self.root.after(150, self._handle_canvas_resize)

    def _handle_canvas_resize(self) -> None:
        self.resize_after_id = None
        if not self.pieces:
            return
        self._cancel_piece_animations()
        self._stop_drag_effects()
        self.active_drag = None
        self._hide_snap_marker()
        self._rebuild_canvas(keep_positions=True)

    def _on_size_changed(self, _event: tk.Event) -> None:
        selected = self.size_combo.current() + 3
        if selected != self.size:
            self.size = selected
            self.start_new_game()

    def choose_image(self) -> None:
        file_path = filedialog.askopenfilename(
            title="选择拼图图片",
            filetypes=(
                ("图片文件", "*.jpg *.jpeg *.png *.webp *.bmp *.gif *.tif *.tiff"),
                ("所有文件", "*.*"),
            ),
        )
        if not file_path:
            return

        try:
            with Image.open(file_path) as source:
                image = ImageOps.exif_transpose(source)
                image = image.convert("RGB")

                # Keep very large photos responsive without changing their aspect ratio.
                max_side = 5000
                if max(image.size) > max_side:
                    ratio = max_side / max(image.size)
                    image = image.resize(
                        (
                            max(1, round(image.width * ratio)),
                            max(1, round(image.height * ratio)),
                        ),
                        RESAMPLE,
                    )
        except Exception as exc:
            messagebox.showerror("无法读取图片", f"请选择有效的图片文件。\n\n{exc}")
            return

        self.original_image = image
        self.source_label = Path(file_path).name
        self.source_var.set(self.source_label)
        self.ready_var.set("本地图片已加载")
        self._set_window_icon()
        self.start_new_game()

    def start_new_game(self) -> None:
        self._cancel_pending_callbacks()
        self.active_drag = None
        self.hint_visible = False
        self.completed = False
        self.moves = 0
        self.started_at = None
        self.finished_at = None
        self.canvas.delete("hint")
        self._update_status()

        if self.canvas.winfo_width() < 100 or self.canvas.winfo_height() < 100:
            self.root.after(100, self.start_new_game)
            return

        self._calculate_board_size()
        self._create_pieces()
        self._rebuild_canvas(keep_positions=False)
        self._animate_deal_in()

    def _cancel_pending_callbacks(self) -> None:
        for attribute in (
            "tick_after_id",
            "hint_after_id",
            "completion_after_id",
            "deal_after_id",
            "drag_effect_after_id",
        ):
            callback_id = getattr(self, attribute)
            if callback_id:
                try:
                    self.root.after_cancel(callback_id)
                except tk.TclError:
                    pass
                setattr(self, attribute, None)
        self._cancel_piece_animations()
        self.is_dealing = False
        self.drag_effects = {}

    def _calculate_board_size(self) -> None:
        canvas_width = max(300, self.canvas.winfo_width())
        canvas_height = max(300, self.canvas.winfo_height())
        available_width = max(220, canvas_width - 46)
        available_height = max(220, canvas_height - 46)
        image_width, image_height = self.original_image.size
        scale = min(available_width / image_width, available_height / image_height)
        display_width = max(1, round(image_width * scale))
        display_height = max(1, round(image_height * scale))

        self.display_image = self.original_image.resize(
            (display_width, display_height),
            RESAMPLE,
        )
        self.board_width = float(display_width)
        self.board_height = float(display_height)
        self.board_left = (canvas_width - self.board_width) / 2
        self.board_top = (canvas_height - self.board_height) / 2
        self.cell_width = self.board_width / self.size
        self.cell_height = self.board_height / self.size

    def _create_pieces(self) -> None:
        total = self.size * self.size
        slots = shuffle_slots(total)
        self.pieces = []

        for piece_id in range(total):
            row, col = divmod(piece_id, self.size)
            slot_index = slots[piece_id]
            slot_row, slot_col = divmod(slot_index, self.size)
            piece = Piece(
                piece_id=piece_id,
                row=row,
                col=col,
                slot_index=slot_index,
                x=slot_col * self.cell_width,
                y=slot_row * self.cell_height,
            )
            self.pieces.append(piece)

    def _piece_box(self, piece: Piece) -> tuple[int, int, int, int]:
        left = round(piece.col * self.board_width / self.size)
        right = round((piece.col + 1) * self.board_width / self.size)
        top = round(piece.row * self.board_height / self.size)
        bottom = round((piece.row + 1) * self.board_height / self.size)
        return left, top, right, bottom

    def _piece_target(self, piece: Piece) -> tuple[float, float]:
        return self._slot_position(piece.row * self.size + piece.col)

    def _piece_size(self, piece: Piece) -> tuple[int, int]:
        left, top, right, bottom = self._piece_box(piece)
        return right - left, bottom - top

    def _slot_position(self, slot_index: int) -> tuple[float, float]:
        row, col = divmod(slot_index, self.size)
        left = round(col * self.board_width / self.size)
        top = round(row * self.board_height / self.size)
        return float(left), float(top)

    def _nearest_available_slot(self, piece: Piece) -> int:
        snapped_slots = {
            candidate.slot_index for candidate in self.pieces if candidate.snapped
        }
        pixel_width, pixel_height = self._piece_size(piece)
        center_x = piece.x + pixel_width / 2
        center_y = piece.y + pixel_height / 2
        best_slot = piece.slot_index
        best_distance = math.inf

        for slot_index in range(self.size * self.size):
            if slot_index in snapped_slots:
                continue
            slot_x, slot_y = self._slot_position(slot_index)
            distance = math.hypot(
                center_x - (slot_x + pixel_width / 2),
                center_y - (slot_y + pixel_height / 2),
            )
            if distance < best_distance:
                best_slot = slot_index
                best_distance = distance

        return best_slot

    def _cancel_piece_animations(self) -> None:
        for callback_id in self.piece_animation_after_ids.values():
            try:
                self.root.after_cancel(callback_id)
            except tk.TclError:
                pass
        self.piece_animation_after_ids = {}

    def _move_piece_to_slot(
        self,
        piece: Piece,
        slot_index: int,
        animate: bool = True,
    ) -> None:
        target_x, target_y = self._slot_position(slot_index)
        piece.slot_index = slot_index

        if not animate:
            piece.x = target_x
            piece.y = target_y
            self._move_piece_items(piece)
            return

        self._animate_piece_to(piece, target_x, target_y)

    def _animate_piece_to(
        self,
        piece: Piece,
        target_x: float,
        target_y: float,
        duration: float = 0.15,
    ) -> None:
        existing_callback = self.piece_animation_after_ids.pop(piece.piece_id, None)
        if existing_callback:
            try:
                self.root.after_cancel(existing_callback)
            except tk.TclError:
                pass

        start_x = piece.x
        start_y = piece.y
        started_at = time.monotonic()

        def step() -> None:
            self.piece_animation_after_ids.pop(piece.piece_id, None)
            try:
                if not self.canvas.winfo_exists() or self.completed:
                    return
                progress = clamp((time.monotonic() - started_at) / duration, 0.0, 1.0)
                eased = 1 - (1 - progress) ** 3
                piece.x = start_x + (target_x - start_x) * eased
                piece.y = start_y + (target_y - start_y) * eased
                self._move_piece_items(piece)
                if progress >= 1.0:
                    piece.x = target_x
                    piece.y = target_y
                    self._move_piece_items(piece)
                    return
                self.piece_animation_after_ids[piece.piece_id] = self.root.after(
                    16,
                    step,
                )
            except tk.TclError:
                return

        step()

    def _rebuild_canvas(self, keep_positions: bool) -> None:
        if not self.pieces or not self.display_image:
            return

        self._stop_drag_effects()

        old_board_width = self.board_width
        old_board_height = self.board_height
        self._calculate_board_size()

        if keep_positions and old_board_width > 0 and old_board_height > 0:
            scale_x = self.board_width / old_board_width
            scale_y = self.board_height / old_board_height
            for piece in self.pieces:
                if not piece.snapped:
                    piece.x *= scale_x
                    piece.y *= scale_y

        self.canvas.delete("all")
        board_right = self.board_left + self.board_width
        board_bottom = self.board_top + self.board_height

        self.canvas.create_rectangle(
            self.board_left - 5,
            self.board_top - 5,
            board_right + 5,
            board_bottom + 5,
            fill="#080b0e",
            outline="",
            tags=("board_shadow",),
        )
        self.canvas.create_rectangle(
            self.board_left - 1,
            self.board_top - 1,
            board_right + 1,
            board_bottom + 1,
            fill="#11161c",
            outline="#485260",
            width=1,
            tags=("board",),
        )

        ordered_pieces = sorted(
            self.pieces,
            key=lambda item: (not item.snapped, item.slot_index),
        )
        for piece in ordered_pieces:
            self._render_piece(piece)

        self.canvas.create_rectangle(
            0,
            0,
            0,
            0,
            outline=COLORS["teal"],
            width=2,
            dash=(5, 4),
            state="hidden",
            tags=("snap_marker",),
        )

        if self.completed:
            self.canvas.delete("piece_outline")

        for piece in self.pieces:
            for item_id in (piece.image_item, piece.outline_item):
                self.canvas.tag_bind(item_id, "<ButtonPress-1>", self._on_piece_press)
                self.canvas.tag_bind(item_id, "<B1-Motion>", self._on_piece_drag)
                self.canvas.tag_bind(item_id, "<ButtonRelease-1>", self._on_piece_release)

    def _render_piece(self, piece: Piece) -> None:
        left, top, right, bottom = self._piece_box(piece)
        crop = self.display_image.crop((left, top, right, bottom))
        piece.source_crop = crop.convert("RGBA")
        piece.photo = ImageTk.PhotoImage(crop)
        pixel_width, pixel_height = self._piece_size(piece)

        if piece.snapped:
            target_x, target_y = self._piece_target(piece)
            piece.x = target_x
            piece.y = target_y
        else:
            maximum_x = max(0.0, self.board_width - pixel_width)
            maximum_y = max(0.0, self.board_height - pixel_height)
            piece.x = clamp(piece.x, 0.0, maximum_x)
            piece.y = clamp(piece.y, 0.0, maximum_y)

        canvas_x = self.board_left + piece.x
        canvas_y = self.board_top + piece.y
        tag = f"piece_{piece.piece_id}"

        piece.image_item = self.canvas.create_image(
            canvas_x,
            canvas_y,
            anchor="nw",
            image=piece.photo,
            tags=(tag, "piece"),
        )
        piece.outline_item = self.canvas.create_rectangle(
            canvas_x,
            canvas_y,
            canvas_x + pixel_width,
            canvas_y + pixel_height,
            outline="#65707e" if not piece.snapped else "#8bd7b0",
            width=1,
            tags=(tag, "piece", "piece_outline"),
        )
        self.canvas.tag_raise(piece.outline_item)

    def _animate_deal_in(self) -> None:
        if self.completed or not self.pieces:
            return

        self.is_dealing = True
        targets: dict[int, tuple[float, float]] = {}
        starts: dict[int, tuple[float, float]] = {}
        center_x = self.board_width / 2
        center_y = self.board_height / 2

        for index, piece in enumerate(self.pieces):
            pixel_width, pixel_height = self._piece_size(piece)
            targets[piece.piece_id] = (piece.x, piece.y)
            start_x = clamp(
                center_x - pixel_width / 2 + random.uniform(-46, 46),
                0.0,
                max(0.0, self.board_width - pixel_width),
            )
            start_y = clamp(
                center_y - pixel_height / 2 + random.uniform(-36, 36),
                0.0,
                max(0.0, self.board_height - pixel_height),
            )
            starts[piece.piece_id] = (start_x, start_y)
            piece.x = start_x
            piece.y = start_y
            self._move_piece_items(piece)

        animation_start = time.monotonic()
        duration = 0.38
        stagger = min(0.11, len(self.pieces) * 0.003)

        def step() -> None:
            if self.completed or not self.pieces or not self.canvas.winfo_exists():
                self.deal_after_id = None
                self.is_dealing = False
                return

            now = time.monotonic()
            complete = True
            for index, piece in enumerate(self.pieces):
                target_x, target_y = targets[piece.piece_id]
                start_x, start_y = starts[piece.piece_id]
                delay = stagger * index
                progress = clamp((now - animation_start - delay) / duration, 0.0, 1.0)
                if progress < 1.0:
                    complete = False

                eased = 1 - (1 - progress) ** 3
                piece.x = start_x + (target_x - start_x) * eased
                piece.y = start_y + (target_y - start_y) * eased
                self._move_piece_items(piece)

            if complete:
                for piece in self.pieces:
                    target_x, target_y = targets[piece.piece_id]
                    piece.x = target_x
                    piece.y = target_y
                    self._move_piece_items(piece)
                self.deal_after_id = None
                self.is_dealing = False
                return

            self.deal_after_id = self.root.after(16, step)

        step()

    def _find_piece_by_item(self, item_id: int) -> Optional[Piece]:
        tags = self.canvas.gettags(item_id)
        for tag in tags:
            if tag.startswith("piece_"):
                try:
                    piece_id = int(tag.split("_", 1)[1])
                except ValueError:
                    return None
                return next(
                    (piece for piece in self.pieces if piece.piece_id == piece_id),
                    None,
                )
        return None

    def _on_piece_press(self, event: tk.Event) -> str:
        item_id = self.canvas.find_withtag("current")
        piece = self._find_piece_by_item(item_id[0]) if item_id else None

        if (
            piece is None
            or piece.snapped
            or self.completed
            or self.hint_visible
            or self.is_dealing
            or piece.piece_id in self.piece_animation_after_ids
            or self.active_drag is not None
        ):
            return "break"

        press_x = event.x - self.board_left
        press_y = event.y - self.board_top
        self.active_drag = {
            "piece": piece,
            "offset_x": press_x - piece.x,
            "offset_y": press_y - piece.y,
            "start_x": piece.x,
            "start_y": piece.y,
            "start_slot": piece.slot_index,
        }
        piece.magnet = False
        self.canvas.tag_raise(piece.image_item)
        self.canvas.tag_raise(piece.outline_item)
        self._start_drag_effects(piece)
        self.canvas.configure(cursor="hand2")
        return "break"

    def _on_piece_drag(self, event: tk.Event) -> str:
        if not self.active_drag:
            return "break"

        piece = self.active_drag["piece"]
        if not isinstance(piece, Piece):
            return "break"

        pixel_width, pixel_height = self._piece_size(piece)
        raw_x = clamp(
            event.x - self.board_left - float(self.active_drag["offset_x"]),
            0.0,
            max(0.0, self.board_width - pixel_width),
        )
        raw_y = clamp(
            event.y - self.board_top - float(self.active_drag["offset_y"]),
            0.0,
            max(0.0, self.board_height - pixel_height),
        )
        target_x, target_y = self._piece_target(piece)
        threshold = max(18.0, min(self.cell_width, self.cell_height) * 0.34)
        distance = math.hypot(raw_x - target_x, raw_y - target_y)

        if distance <= threshold:
            piece.magnet = True
            piece.x = target_x
            piece.y = target_y
            self._move_piece_items(piece)
            self._show_snap_marker(piece)
        else:
            piece.magnet = False
            piece.x = raw_x
            piece.y = raw_y
            self._move_piece_items(piece)

            if distance <= threshold * 1.45:
                self._show_snap_marker(piece)
            else:
                self._hide_snap_marker()

        self._move_drag_effects(piece)
        self._maybe_add_drag_trail(piece)
        return "break"

    def _on_piece_release(self, _event: tk.Event) -> str:
        if not self.active_drag:
            return "break"

        piece = self.active_drag["piece"]
        if not isinstance(piece, Piece):
            self.active_drag = None
            return "break"

        if piece.magnet:
            self._snap_piece(piece, self.active_drag)
            self.moves += 1
            self._start_timer_if_needed()
            self._update_status()
            self._check_completion()
        else:
            piece.magnet = False
            self._settle_free_piece(piece, self.active_drag)

        self._stop_drag_effects()
        self.active_drag = None
        self.canvas.configure(cursor="arrow")
        self._hide_snap_marker()
        self._restore_piece_layers()
        return "break"

    def _move_piece_items(self, piece: Piece) -> None:
        pixel_width, pixel_height = self._piece_size(piece)
        canvas_x = self.board_left + piece.x
        canvas_y = self.board_top + piece.y
        self.canvas.coords(piece.image_item, canvas_x, canvas_y)
        self.canvas.coords(
            piece.outline_item,
            canvas_x,
            canvas_y,
            canvas_x + pixel_width,
            canvas_y + pixel_height,
        )

    def _start_drag_effects(self, piece: Piece) -> None:
        self._stop_drag_effects()
        pixel_width, pixel_height = self._piece_size(piece)
        canvas_x = self.board_left + piece.x
        canvas_y = self.board_top + piece.y
        shadow_item = self.canvas.create_rectangle(
            canvas_x + 8,
            canvas_y + 8,
            canvas_x + pixel_width + 8,
            canvas_y + pixel_height + 8,
            fill="#05070a",
            outline="",
            stipple="gray50",
            tags=("drag_effect",),
        )
        self.canvas.tag_lower(shadow_item, piece.image_item)
        self.drag_effects = {
            "piece": piece,
            "shadow": shadow_item,
            "trails": [],
            "last_trail_at": 0.0,
            "last_trail_x": piece.x,
            "last_trail_y": piece.y,
        }
        self._animate_drag_effects()

    def _move_drag_effects(self, piece: Piece) -> None:
        shadow_item = self.drag_effects.get("shadow")
        if not isinstance(shadow_item, int):
            return

        pixel_width, pixel_height = self._piece_size(piece)
        canvas_x = self.board_left + piece.x
        canvas_y = self.board_top + piece.y
        try:
            self.canvas.coords(
                shadow_item,
                canvas_x + 8,
                canvas_y + 8,
                canvas_x + pixel_width + 8,
                canvas_y + pixel_height + 8,
            )
        except tk.TclError:
            self._stop_drag_effects()

    def _animate_drag_effects(self) -> None:
        if self.active_drag is None:
            self.drag_effect_after_id = None
            return

        self.drag_effect_after_id = None
        piece = self.drag_effects.get("piece")
        if not isinstance(piece, Piece):
            return

        phase = (time.monotonic() * 6.5) % (math.tau)
        pulse = (math.sin(phase) + 1) / 2
        outline = "#72f2dc" if piece.magnet else COLORS["teal"]
        width = 2 + round(pulse * (2 if piece.magnet else 1))
        try:
            if self.canvas.type(piece.outline_item):
                self.canvas.itemconfigure(
                    piece.outline_item,
                    outline=outline,
                    width=width,
                )
        except tk.TclError:
            return

        try:
            if self.canvas.find_withtag("snap_marker"):
                self.canvas.itemconfigure(
                    "snap_marker",
                    outline="#72f2dc" if piece.magnet else COLORS["teal"],
                    width=3 if piece.magnet else 2,
                    dashoffset=int((time.monotonic() * 42) % 18),
                )
        except tk.TclError:
            pass

        self._prune_drag_trails()
        self.drag_effect_after_id = self.root.after(33, self._animate_drag_effects)

    def _maybe_add_drag_trail(self, piece: Piece) -> None:
        source = piece.source_crop
        if source is None or not self.drag_effects:
            return

        now = time.monotonic()
        last_time = float(self.drag_effects.get("last_trail_at", 0.0))
        last_x = float(self.drag_effects.get("last_trail_x", piece.x))
        last_y = float(self.drag_effects.get("last_trail_y", piece.y))
        distance = math.hypot(piece.x - last_x, piece.y - last_y)

        if now - last_time < 0.045 or distance < 9:
            return

        opacity = clamp(0.10 + distance / 260, 0.10, 0.24)
        trail_image = source.copy()
        alpha = trail_image.getchannel("A")
        trail_image.putalpha(alpha.point(lambda value: round(value * opacity)))
        trail_photo = ImageTk.PhotoImage(trail_image)
        trail_item = self.canvas.create_image(
            self.board_left + piece.x,
            self.board_top + piece.y,
            anchor="nw",
            image=trail_photo,
            tags=("drag_effect", "drag_trail"),
        )
        self.canvas.tag_lower(trail_item, piece.image_item)

        trails = self.drag_effects["trails"]
        if isinstance(trails, list):
            trails.append((trail_item, trail_photo, now))
            while len(trails) > 5:
                old_item, _old_photo, _created_at = trails.pop(0)
                try:
                    self.canvas.delete(old_item)
                except tk.TclError:
                    pass

        self.drag_effects["last_trail_at"] = now
        self.drag_effects["last_trail_x"] = piece.x
        self.drag_effects["last_trail_y"] = piece.y

    def _prune_drag_trails(self) -> None:
        trails = self.drag_effects.get("trails")
        if not isinstance(trails, list):
            return

        now = time.monotonic()
        live_trails = []
        for item_id, photo, created_at in trails:
            if now - created_at <= 0.18:
                live_trails.append((item_id, photo, created_at))
                continue
            try:
                self.canvas.delete(item_id)
            except tk.TclError:
                pass
        self.drag_effects["trails"] = live_trails

    def _stop_drag_effects(self) -> None:
        if self.drag_effect_after_id:
            try:
                self.root.after_cancel(self.drag_effect_after_id)
            except tk.TclError:
                pass
            self.drag_effect_after_id = None

        piece = self.drag_effects.get("piece")
        shadow_item = self.drag_effects.get("shadow")
        if isinstance(shadow_item, int):
            try:
                self.canvas.delete(shadow_item)
            except tk.TclError:
                pass

        trails = self.drag_effects.get("trails")
        if isinstance(trails, list):
            for item_id, _photo, _created_at in trails:
                try:
                    self.canvas.delete(item_id)
                except tk.TclError:
                    pass

        if isinstance(piece, Piece) and not piece.snapped:
            try:
                if self.canvas.type(piece.outline_item):
                    self.canvas.itemconfigure(
                        piece.outline_item,
                        outline="#65707e",
                        width=1,
                    )
            except tk.TclError:
                pass

        self.drag_effects = {}

    def _show_snap_marker(self, piece: Piece) -> None:
        target_x, target_y = self._piece_target(piece)
        pixel_width, pixel_height = self._piece_size(piece)
        self.canvas.coords(
            "snap_marker",
            self.board_left + target_x,
            self.board_top + target_y,
            self.board_left + target_x + pixel_width,
            self.board_top + target_y + pixel_height,
        )
        self.canvas.itemconfigure("snap_marker", state="normal")
        self.canvas.tag_raise("snap_marker")

    def _hide_snap_marker(self) -> None:
        if self.canvas.find_withtag("snap_marker"):
            self.canvas.itemconfigure("snap_marker", state="hidden")

    def _settle_free_piece(self, piece: Piece, drag: dict[str, object]) -> None:
        target_slot = self._nearest_available_slot(piece)
        start_slot = int(drag.get("start_slot", piece.slot_index))
        occupant = next(
            (
                candidate
                for candidate in self.pieces
                if candidate is not piece
                and not candidate.snapped
                and candidate.slot_index == target_slot
            ),
            None,
        )

        if occupant is not None and target_slot != start_slot:
            self._move_piece_to_slot(occupant, start_slot, animate=True)

        self._move_piece_to_slot(piece, target_slot, animate=True)

    def _snap_piece(self, piece: Piece, drag: dict[str, object]) -> None:
        target_x, target_y = self._piece_target(piece)
        target_slot = piece.row * self.size + piece.col
        start_slot = int(drag.get("start_slot", piece.slot_index))
        occupied_piece = next(
            (
                candidate
                for candidate in self.pieces
                if candidate is not piece
                and not candidate.snapped
                and candidate.slot_index == target_slot
            ),
            None,
        )

        if occupied_piece is not None:
            self._move_piece_to_slot(occupied_piece, start_slot, animate=True)

        piece.snapped = True
        piece.magnet = False
        piece.slot_index = target_slot
        piece.x = target_x
        piece.y = target_y
        self._move_piece_items(piece)
        self.canvas.itemconfigure(piece.outline_item, outline="#8bd7b0")
        self._pulse_snapped_piece(piece)

    def _pulse_snapped_piece(self, piece: Piece) -> None:
        pulse_steps = (
            (0, "#72f2dc", 3),
            (70, "#33c6b5", 2),
            (140, "#8bd7b0", 1),
        )

        def apply_style(outline: str, width: int) -> None:
            try:
                if self.canvas.type(piece.outline_item):
                    self.canvas.itemconfigure(
                        piece.outline_item,
                        outline=outline,
                        width=width,
                    )
            except tk.TclError:
                pass

        for delay, outline, width in pulse_steps:
            self.root.after(delay, lambda o=outline, w=width: apply_style(o, w))

    def _restore_piece_layers(self) -> None:
        for piece in self.pieces:
            if not piece.snapped:
                self.canvas.tag_raise(piece.image_item)
                self.canvas.tag_raise(piece.outline_item)
        self.canvas.tag_raise("snap_marker")

    def _start_timer_if_needed(self) -> None:
        if self.started_at is None:
            self.started_at = time.monotonic()
            self._schedule_tick()

    def _schedule_tick(self) -> None:
        if self.tick_after_id:
            return
        self.tick_after_id = self.root.after(250, self._tick)

    def _tick(self) -> None:
        self.tick_after_id = None
        self._update_status()
        if not self.completed and self.started_at is not None:
            self._schedule_tick()

    def _update_status(self) -> None:
        total = self.size * self.size
        solved = sum(1 for piece in self.pieces if piece.snapped)
        elapsed = 0.0
        if self.started_at is not None:
            elapsed = (self.finished_at or time.monotonic()) - self.started_at

        self.progress_var.set(f"{solved} / {total}")
        self.time_var.set(format_time(elapsed))
        self.move_var.set(str(self.moves))
        self.progress_bar["value"] = (solved / total * 100) if total else 0

    def _check_completion(self) -> None:
        if self.completed or any(not piece.snapped for piece in self.pieces):
            return

        self.completed = True
        self.finished_at = time.monotonic()
        if self.tick_after_id:
            try:
                self.root.after_cancel(self.tick_after_id)
            except tk.TclError:
                pass
            self.tick_after_id = None
        self._hide_hint()
        self.canvas.delete("piece_outline")
        self._update_status()
        self.completion_after_id = self.root.after(220, self._show_completion_dialog)

    def show_hint(self) -> None:
        if self.completed or self.hint_visible or not self.display_image:
            return

        self._hide_hint()
        self.hint_photo = ImageTk.PhotoImage(self.display_image)
        self.canvas.create_image(
            self.board_left,
            self.board_top,
            anchor="nw",
            image=self.hint_photo,
            tags=("hint",),
        )
        self.canvas.create_rectangle(
            self.board_left,
            self.board_top,
            self.board_left + self.board_width,
            self.board_top + self.board_height,
            outline=COLORS["gold"],
            width=3,
            tags=("hint",),
        )
        badge_left = self.board_left + 12
        badge_top = self.board_top + 12
        self.canvas.create_rectangle(
            badge_left,
            badge_top,
            badge_left + 76,
            badge_top + 28,
            fill=COLORS["gold"],
            outline="",
            tags=("hint",),
        )
        self.canvas.create_text(
            badge_left + 38,
            badge_top + 14,
            text="原图提示",
            fill="#211a05",
            font=("Microsoft YaHei UI", 9, "bold"),
            tags=("hint",),
        )
        self.canvas.tag_raise("hint")
        self.hint_visible = True
        self.hint_after_id = self.root.after(1500, self._hide_hint)

    def _hide_hint(self) -> None:
        if self.hint_after_id:
            try:
                self.root.after_cancel(self.hint_after_id)
            except tk.TclError:
                pass
            self.hint_after_id = None
        if self.canvas.find_withtag("hint"):
            self.canvas.delete("hint")
        self.hint_visible = False

    def _show_completion_dialog(self) -> None:
        self.completion_after_id = None
        if not self.completed:
            return

        elapsed = (self.finished_at or time.monotonic()) - (
            self.started_at or time.monotonic()
        )
        dialog = tk.Toplevel(self.root)
        dialog.title("拼图完成")
        dialog.configure(bg=COLORS["surface"])
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        body = tk.Frame(dialog, bg=COLORS["surface"], padx=30, pady=26)
        body.pack(fill="both", expand=True)

        mark = tk.Canvas(
            body,
            width=64,
            height=64,
            bg=COLORS["surface"],
            highlightthickness=0,
        )
        mark.pack()
        mark.create_oval(
            2,
            2,
            62,
            62,
            outline=COLORS["success"],
            width=2,
            fill="#172820",
        )
        mark.create_line(
            18,
            33,
            28,
            43,
            47,
            22,
            fill=COLORS["success"],
            width=4,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND,
        )

        tk.Label(
            body,
            text="拼图完成",
            bg=COLORS["surface"],
            fg=COLORS["text"],
            font=("Microsoft YaHei UI", 19, "bold"),
        ).pack(pady=(14, 0))
        tk.Label(
            body,
            text="整张图片已经完整还原。",
            bg=COLORS["surface"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 10),
        ).pack(pady=(6, 18))

        summary = tk.Frame(
            body,
            bg=COLORS["surface_strong"],
            highlightbackground=COLORS["line"],
            highlightthickness=1,
            padx=18,
            pady=14,
        )
        summary.pack(fill="x")
        summary.grid_columnconfigure(0, weight=1)
        summary.grid_columnconfigure(1, weight=1)
        self._add_dialog_stat(summary, 0, "完成时间", format_time(elapsed))
        self._add_dialog_stat(summary, 1, "拖动步数", str(self.moves))

        actions = tk.Frame(body, bg=COLORS["surface"])
        actions.pack(pady=(20, 0))

        play_again = ttk.Button(
            actions,
            text="再玩一次",
            style="Accent.TButton",
            command=lambda: (dialog.destroy(), self.start_new_game()),
        )
        play_again.pack(side="left")

        close_button = ttk.Button(
            actions,
            text="关闭",
            command=dialog.destroy,
        )
        close_button.pack(side="left", padx=(10, 0))

        dialog.update_idletasks()
        width = dialog.winfo_reqwidth()
        height = dialog.winfo_reqheight()
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()
        x = root_x + max(0, (root_width - width) // 2)
        y = root_y + max(0, (root_height - height) // 2)
        dialog.geometry(f"+{x}+{y}")
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.focus_set()

    def _add_dialog_stat(
        self,
        parent: tk.Frame,
        column: int,
        label_text: str,
        value_text: str,
    ) -> None:
        frame = tk.Frame(parent, bg=COLORS["surface_strong"])
        frame.grid(row=0, column=column, sticky="nsew", padx=12)
        tk.Label(
            frame,
            text=label_text,
            bg=COLORS["surface_strong"],
            fg=COLORS["muted"],
            font=("Microsoft YaHei UI", 9),
        ).pack()
        tk.Label(
            frame,
            text=value_text,
            bg=COLORS["surface_strong"],
            fg=COLORS["text"],
            font=("Consolas", 16, "bold"),
        ).pack(pady=(5, 0))


def run_self_test() -> int:
    enable_windows_high_dpi()
    artwork = create_default_artwork(320, 220)
    assert artwork.size == (320, 220)

    for count in (9, 16, 25, 36):
        slots = shuffle_slots(count)
        assert sorted(slots) == list(range(count))
        assert all(slot != index for index, slot in enumerate(slots))

    root = tk.Tk()
    root.geometry("1100x760+0+0")
    app = JigsawApp(root)
    root.update_idletasks()
    root.update()
    app.start_new_game()
    root.update()

    assert len(app.pieces) == 9
    assert app.source_label == "内置示例图"

    test_piece = app.pieces[0]
    app.active_drag = {
        "piece": test_piece,
        "offset_x": 0.0,
        "offset_y": 0.0,
        "start_x": test_piece.x,
        "start_y": test_piece.y,
        "start_slot": test_piece.slot_index,
    }
    app._start_drag_effects(test_piece)
    test_piece.x += 12
    test_piece.y += 8
    app._move_drag_effects(test_piece)
    app._maybe_add_drag_trail(test_piece)
    root.update()
    app._settle_free_piece(test_piece, app.active_drag)
    root.update()
    app._cancel_piece_animations()
    app._stop_drag_effects()
    app.active_drag = None
    assert len({item.slot_index for item in app.pieces}) == len(app.pieces)

    print(
        "Self-test passed: artwork, shuffling, Tkinter UI, "
        "deal-in animation, and drag effects initialized."
    )
    root.destroy()
    return 0


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="运行无交互自检后退出。",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{APP_TITLE} {APP_VERSION}",
    )
    return parser.parse_args(argv)


def main() -> int:
    enable_windows_high_dpi()
    args = parse_args()
    if args.self_test:
        return run_self_test()

    root = tk.Tk()
    JigsawApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
