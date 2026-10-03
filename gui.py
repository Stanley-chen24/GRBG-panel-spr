"""General image viewer GUI

視窗架構：
    root      : 顯示視窗，將視窗移至 Panel 螢幕上
    ctrl_win  : 控制視窗與縮圖預覽

影像處理管線 (panel_type == "121" 時) 給 panels/lextar_121.py
本檔案只負責Tkinter 視窗、狀態機、跟哪個 panel 模組對應。
"""

import tkinter as tk
from tkinter import ttk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageOps

from panels import lextar_121

try:
    from screeninfo import get_monitors
except ImportError:          # 沒裝 screeninfo 也能跑，只是第二螢幕改用手動
    get_monitors = None

ALGORITHMS = ["DPD", "DSD", "MMSE"]
INFO_BAR_HEIGHT = 40              # 新增文字列的高度 (px)，依面板可視空間調整
INFO_FONT_PATH = r"C:\Windows\Fonts\times.ttf"   # Times New Roman
INFO_FONT_COLOR = "white"
PREVIEW_SIZE = 540


class ImageViewer:
    def __init__(self, root):
        self.root = root
        self.img_list = []          # 載入的圖檔路徑
        self.idx = 0                # 目前顯示第幾張
        self.panel_type = "regular"  # regular: 已經帶有自身SPR的面板，所以直接給正常訊號 (H,W,3)
        self.side_by_side = False    # 並排比較演算法
        self.algo_single = ALGORITHMS[0]  # 非 side-by-side 時，單張顯示要用哪個 SPR 演算法
        self.algo_left = ALGORITHMS[0]
        self.algo_right = ALGORITHMS[1]
        self.fullscreen = False
        self._side_split_x = None   
        self.on_image_changed = None
        self._photo = None          
        self.image_label = tk.Label(root, bg="black")
        self.image_label.pack(anchor="nw")

        root.bind("<Left>", self.prev_image)
        root.bind("<Right>", self.next_image)
        root.bind("f", self.toggle_fullscreen)
        root.bind("<Escape>", self.quit_app)

    def _to_panel_format(self, out_spr):
        """依目前 panel_type，把 SPR 輸出轉成「該面板實際要吃的格式」。"""
        if self.panel_type == "121":
            out_panel = lextar_121.convert_to_panel(out_spr)
        else:
            out_panel = np.uint8(np.clip(out_spr, 0, 255))  # regular: 不用幾何搬移
        return Image.fromarray(out_panel)

    def _apply_panel(self, img, algo_name):
        """影像路徑：指定的 SPR 演算法 -> 面板格式轉換。
        單張顯示與 side-by-side 共用，差別只在帶進來的 algo_name。
        """
        arr = np.asarray(img, dtype=np.float32)
        out_spr = lextar_121.spr_algorithm(arr, algo_name) if self.panel_type == "121" else arr
        return self._to_panel_format(out_spr)

    def _compose(self, src):
        """把來源影像轉成「要顯示在 media 視窗的那一張合成影像」。"""
        if not self.side_by_side:
            self._side_split_x = None   # 沒有並排，就沒有分界線
            return self._apply_panel(src, self.algo_single)

        # 並排：左右各跑一種演算法，再用 PIL 併成一張大圖
        left = self._apply_panel(src, self.algo_left)
        right = self._apply_panel(src, self.algo_right)
        canvas = Image.new("RGB",
                           (left.width + right.width,
                            max(left.height, right.height)),
                           "black")
        canvas.paste(left, (0, 0))
        canvas.paste(right, (left.width, 0))
        self._side_split_x = left.width   
        return canvas

    def _draw_algo_label(self, composite):
        if self.panel_type != "121":
            return composite

        w, h = composite.size
        out = Image.new("RGB", (w, h + INFO_BAR_HEIGHT), "black")
        out.paste(composite, (0, 0))    

        if self.side_by_side:
            split = self._side_split_x or (w // 2)
            self._draw_centered_text(draw, self.algo_left, 0, split, h)
            self._draw_centered_text(draw, self.algo_right, split, w, h)
        else:
            self._draw_centered_text(draw, self.algo_single, 0, w, h)
        return out

    def _draw_centered_text(self, draw, text, x0, x1, bar_top):
        """畫SPR演算法名稱文字並置中擺放"""
        if not text:
            return
        box_w = x1 - x0

        size = max(8, int(INFO_BAR_HEIGHT * 0.6))
        font = ImageFont.truetype(INFO_FONT_PATH, size)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        while (text_w > box_w * 0.9 or text_h > INFO_BAR_HEIGHT * 0.9) and size > 8:
            size -= 1
            font = ImageFont.truetype(INFO_FONT_PATH, size)
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

        x = x0 + (box_w - text_w) // 2 - bbox[0]
        y = bar_top + (INFO_BAR_HEIGHT - text_h) // 2 - bbox[1]
        draw.text((x, y), text, font=font, fill=INFO_FONT_COLOR)

    def show_current(self):
        """重畫：五種會改變畫面的操作，最後都呼叫這個。"""
        if not self.img_list:
            return

        src = Image.open(self.img_list[self.idx]).convert("RGB")
        composite = self._compose(src)
        composite = self._draw_algo_label(composite)

        self._photo = ImageTk.PhotoImage(composite)
        self.image_label.config(image=self._photo)
        if self.on_image_changed is not None:
            self.on_image_changed(src)

    # user operation: load / next / prev / quit / toggle_fullscreen
    def load_images(self, event=None, parent=None):
        paths = filedialog.askopenfilenames(
            title="Select Images",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff")],
            parent=parent)
        if paths:
            self.img_list = list(paths)
            self.idx = 0
            self.show_current()

    def prev_image(self, event=None):
        if self.img_list:
            self.idx = (self.idx - 1) % len(self.img_list)
            self.show_current()

    def next_image(self, event=None):
        if self.img_list:
            self.idx = (self.idx + 1) % len(self.img_list)
            self.show_current()

    def toggle_fullscreen(self, event=None):
        if self.root.overrideredirect():
            self._windowed()
            return
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)

    def exit_fullscreen(self, event=None):
        if self.root.overrideredirect() or self.fullscreen:
            self.toggle_fullscreen()

    def move_to_second_screen(self, event=None):
        monitors = get_monitors() if get_monitors else []
        externals = [m for m in monitors if not m.is_primary]

        if not externals:
            messagebox.showinfo(
                "Second screen",
                "偵測不到第二螢幕。\n"
                "請確認 Win+P 已選「延伸」模式，或按 F 全螢幕後用 "
                "Win+Shift+←/→ 手動移動。")
            return

        self._target = externals[0]
        self.root.attributes("-fullscreen", False)
        self.root.overrideredirect(False)
        m = self._target
        self.root.geometry(f"{m.width}x{m.height}+{m.x}+{m.y}")
        self.root.after(200, self._lock_on_target)

    def _lock_on_target(self):
        m = self._target
        self.root.overrideredirect(True)                 # remove title bar
        self.root.geometry(f"{m.width}x{m.height}+{m.x}+{m.y}")
        self.root.focus_force()
        self.fullscreen = True

    def _windowed(self):
        self.root.overrideredirect(False)
        self.root.attributes("-fullscreen", False)
        self.root.geometry("900x600+100+100")
        self.fullscreen = False

    def quit_app(self, event=None):
        self.root.destroy()


class ControlPanel:
    def __init__(self, root, viewer):
        self.root = root
        self.viewer = viewer
        self.root.title("Controls")
        self._thumb_photo = None    
        self._build_widgets()
        self._bind_keys()

    def _build_widgets(self):
        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        left = ttk.Frame(self.root)
        left.grid(row=0, column=0, sticky="nsew")
        right = ttk.Frame(self.root)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 6), pady=6)

        row_file = ttk.Frame(left)
        row_file.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Button(row_file, text="Load Images",
           command=lambda: self.viewer.load_images(parent=self.root)).pack(side="left")

        # --- Next/Previous ---
        row_nav = ttk.Frame(left)
        row_nav.pack(fill="x", padx=10, pady=4)
        ttk.Button(row_nav, text="Previous",
                   command=self.viewer.prev_image).pack(side="left", padx=(0, 4))
        ttk.Button(row_nav, text="Next",
                   command=self.viewer.next_image).pack(side="left")

        # --- Display Control ---
        row_disp = ttk.Frame(left)
        row_disp.pack(fill="x", padx=10, pady=4)
        ttk.Button(row_disp, text="Second Screen",
                   command=self.viewer.move_to_second_screen).pack(side="left", padx=(0, 4))
        ttk.Button(row_disp, text="Exit Fullscreen",
                   command=self.viewer.exit_fullscreen).pack(side="left")

        # --- Panel Type ---
        ttk.Label(left, text="Panel Type").pack(anchor="w", padx=10, pady=(10, 0))
        row_pt = ttk.Frame(left)
        row_pt.pack(fill="x", padx=10, pady=(0, 4))
        self.panel_type_var = tk.StringVar(value=self.viewer.panel_type)
        for text, value in (("regular", "regular"), ("Lextar", "121")):
            ttk.Radiobutton(row_pt, text=text, value=value,
                            variable=self.panel_type_var,
                            command=self._on_panel_type).pack(side="left")

        # --- SPR Algorithm buttons (非 side-by-side 時，選單張顯示要用哪種
        #     演算法；只有 Lextar panel 才有得選，因為 regular 設定是面板本身自帶 SPR，
        self.row_algo_single = ttk.Frame(left)
        self.algo_single_var = tk.StringVar(value=self.viewer.algo_single)
        for name in ALGORITHMS:
            ttk.Radiobutton(self.row_algo_single, text=name, value=name,
                            variable=self.algo_single_var,
                            command=self._on_algo_single_change).pack(side="left")
        # Side-by-side
        self.row_sbs = ttk.Frame(left)
        self.sbs_var = tk.BooleanVar(value=self.viewer.side_by_side)
        ttk.Checkbutton(self.row_sbs, text="Side-by-side compare",
                        variable=self.sbs_var,
                        command=self._on_sbs_toggle).pack(side="left")
        # Algorithm Selection
        self.row_algo = ttk.Frame(left)
        line_left = ttk.Frame(self.row_algo)
        line_left.pack(fill="x", pady=(0, 2))
        ttk.Label(line_left, text="Left ", width=6).pack(side="left")
        self.algo_left_var = tk.StringVar(value=self.viewer.algo_left)
        self.cb_left = ttk.Combobox(line_left, textvariable=self.algo_left_var,
                                    values=ALGORITHMS, state="readonly", width=12)
        self.cb_left.pack(side="left")

        line_right = ttk.Frame(self.row_algo)
        line_right.pack(fill="x")
        ttk.Label(line_right, text="Right", width=6).pack(side="left")
        self.algo_right_var = tk.StringVar(value=self.viewer.algo_right)
        self.cb_right = ttk.Combobox(line_right, textvariable=self.algo_right_var,
                                     values=ALGORITHMS, state="readonly", width=12)
        self.cb_right.pack(side="left")

        self.cb_left.bind("<<ComboboxSelected>>", self._on_algo_change)
        self.cb_right.bind("<<ComboboxSelected>>", self._on_algo_change)

        # --- Exit ---
        self.btn_quit = ttk.Button(left, text="Quit", command=self.viewer.quit_app)
        self.btn_quit.pack(anchor="w", padx=10, pady=(12, 10))
        self._update_sbs_visibility()

        ttk.Label(right, text="Original image").pack(anchor="w")
        box = tk.Frame(right, width=PREVIEW_SIZE, height=PREVIEW_SIZE, bg="black")
        box.pack(pady=(2, 0))
        box.pack_propagate(False)
        self.preview_label = tk.Label(box, bg="black")
        self.preview_label.pack(fill="both", expand=True)

    def _bind_keys(self):
        self.root.bind("<Left>", self.viewer.prev_image)
        self.root.bind("<Right>", self.viewer.next_image)
        self.root.bind("f", self.viewer.toggle_fullscreen)
        self.root.bind("<Escape>", self.viewer.quit_app)

    # Callbacks for GUI events
    def _on_panel_type(self):
        self.viewer.panel_type = self.panel_type_var.get()
        self._update_sbs_visibility()
        self.viewer.show_current()

    def _update_sbs_visibility(self):
        """side-by-side 時隱藏SPR選擇按鈕"""
        if self.viewer.panel_type == "121":
            self.row_sbs.pack(fill="x", padx=10, pady=(6, 0), before=self.btn_quit)
        else:
            self.row_sbs.pack_forget()
            self.row_algo.pack_forget()
            self.sbs_var.set(False)
            self.viewer.side_by_side = False
        self._update_algo_single_visibility()

    def _update_algo_single_visibility(self):
        if self.viewer.panel_type == "121" and not self.viewer.side_by_side:
            self.row_algo_single.pack(fill="x", padx=10, pady=(6, 0),
                                      before=self.row_sbs)
        else:
            self.row_algo_single.pack_forget()

    def _on_sbs_toggle(self):
        self.viewer.side_by_side = self.sbs_var.get()
        if self.viewer.side_by_side:
            self.row_algo.pack(fill="x", padx=10, pady=(0, 4),
                               before=self.btn_quit)
        else:
            self.row_algo.pack_forget()
        self._update_algo_single_visibility()
        self.viewer.show_current()

    def _on_algo_change(self, event=None):
        self.viewer.algo_left = self.algo_left_var.get()
        self.viewer.algo_right = self.algo_right_var.get()
        self.viewer.show_current()

    def _on_algo_single_change(self):
        self.viewer.algo_single = self.algo_single_var.get()
        self.viewer.show_current()

    def update_thumbnail(self, pil_image):
        thumb = ImageOps.fit(pil_image, (PREVIEW_SIZE, PREVIEW_SIZE), Image.LANCZOS)
        self._thumb_photo = ImageTk.PhotoImage(thumb)
        self.preview_label.config(image=self._thumb_photo)
