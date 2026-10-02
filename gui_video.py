"""影片版 GUI：繼承 gui.py 的 ImageViewer / ControlPanel，只加播放與時間軸。

影像合成 (SPR -> 面板格式 -> 演算法名稱列) 全部沿用父類別，
這裡只負責逐幀讀取、播放時鐘、暫停與跳轉。
"""

import time
import tkinter as tk
from tkinter import ttk
import tkinter.filedialog as filedialog

import cv2
from PIL import Image, ImageTk

from gui import ImageViewer, ControlPanel


class VideoViewer(ImageViewer):
    """media 視窗：img_list / idx 沿用為影片清單 / 目前第幾支。"""

    def __init__(self, root):
        super().__init__(root)
        self.cap = None
        self.fps = 30.0
        self.n_frames = 0
        self.cur = -1               # 目前顯示的幀編號
        self.playing = False
        self.dragging = False       # 拖時間軸時暫停自動前進
        self._src = None            # 目前幀 (PIL RGB)，供切換設定時重繪
        self._job = None            # after() 排程 id
        self._t0 = 0.0              # 播放時鐘起點 (wall clock)
        self._f0 = 0                # 時鐘起點對應的幀編號

        self.on_progress = None     # (cur, n_frames, fps)
        self.on_play_state = None   # (playing)

        root.bind("<space>", self.toggle_play)

    # ------------------------------------------------------------------
    # 載入 / 切換影片
    # ------------------------------------------------------------------
    def load_images(self, event=None, parent=None):
        paths = filedialog.askopenfilenames(
            title="Select Videos",
            filetypes=[("Video Files", "*.mp4;*.avi;*.mkv;*.mov")],
            parent=parent)
        if paths:
            self.img_list = list(paths)
            self.idx = 0
            self._open(play=True)

    def prev_image(self, event=None):
        if self.img_list:
            self.idx = (self.idx - 1) % len(self.img_list)
            self._open(play=self.playing)

    def next_image(self, event=None):
        if self.img_list:
            self.idx = (self.idx + 1) % len(self.img_list)
            self._open(play=self.playing)

    def _open(self, play):
        self._cancel()
        if self.cap:
            self.cap.release()
        self.cap = cv2.VideoCapture(self.img_list[self.idx])
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.n_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.cur = -1
        self.seek(0)
        self.set_playing(play)

    # ------------------------------------------------------------------
    # 播放控制
    # ------------------------------------------------------------------
    def toggle_play(self, event=None):
        if self.cap:
            self.set_playing(not self.playing)

    def set_playing(self, flag):
        self.playing = flag
        self._cancel()
        if flag:
            self._restart_clock(max(self.cur, 0))
            self._schedule()
        if self.on_play_state:
            self.on_play_state(flag)

    def seek(self, i):
        i = max(0, min(i, self.n_frames - 1))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, frame = self.cap.read()
        if not ok:
            return
        self.cur = i
        self._restart_clock(i)
        self._render(frame)

    def end_drag(self):
        self.dragging = False
        self._restart_clock(max(self.cur, 0))

    def _restart_clock(self, frame_idx):
        self._t0 = time.perf_counter()
        self._f0 = frame_idx

    def _cancel(self):
        if self._job is not None:
            self.root.after_cancel(self._job)
            self._job = None

    def _schedule(self):
        due = (self.cur + 1 - self._f0) / self.fps - (time.perf_counter() - self._t0)
        self._job = self.root.after(max(1, int(due * 1000)), self._tick)

    def _tick(self):
        self._job = None
        if not self.playing:
            return
        if self.dragging:
            self._job = self.root.after(30, self._tick)
            return

        # 依實際經過時間決定該顯示哪一幀，跟不上就丟幀 (grab 跳過)
        target = self._f0 + int((time.perf_counter() - self._t0) * self.fps)
        if target >= self.n_frames:
            self.seek(0)            # 循環播放
        elif target > self.cur:
            for _ in range(target - self.cur - 1):
                self.cap.grab()
            ok, frame = self.cap.read()
            if ok:
                self.cur = target
                self._render(frame)
            else:
                self.seek(0)
        self._schedule()

    # ------------------------------------------------------------------
    # 顯示
    # ------------------------------------------------------------------
    def _render(self, bgr):
        self._src = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        self.show_current()

    def show_current(self):
        if self._src is None:
            return
        composite = self._draw_algo_label(self._compose(self._src))
        self._photo = ImageTk.PhotoImage(composite)
        self.image_label.config(image=self._photo)
        if self.on_image_changed:
            self.on_image_changed(self._src)
        if self.on_progress:
            self.on_progress(self.cur, self.n_frames, self.fps)

    def quit_app(self, event=None):
        self._cancel()
        if self.cap:
            self.cap.release()
        super().quit_app()


def _fmt(sec):
    sec = int(sec)
    return f"{sec // 60:02d}:{sec % 60:02d}"


class VideoControlPanel(ControlPanel):
    """沿用圖片版所有控制項，額外加 Play/Pause 與時間軸。"""

    def _build_widgets(self):
        super()._build_widgets()
        left = self.btn_quit.master
        rows = left.winfo_children()
        rows[0].winfo_children()[0].config(text="Load Videos")  # 原 "Load Images"

        # --- Play / Pause + 時間 ---
        row_play = ttk.Frame(left)
        row_play.pack(fill="x", padx=10, pady=(8, 0), after=rows[1])
        self.btn_play = ttk.Button(row_play, text="Play", takefocus=False,
                                   command=self.viewer.toggle_play)
        self.btn_play.pack(side="left")
        self.lbl_time = ttk.Label(row_play, text="00:00 / 00:00")
        self.lbl_time.pack(side="left", padx=8)

        # --- 時間軸 ---
        row_seek = ttk.Frame(left)
        row_seek.pack(fill="x", padx=10, pady=(2, 4), after=row_play)
        self._n = 0
        self._ui = False            # True 時是程式在更新滑桿，不當成使用者拖曳
        self.seek_var = tk.DoubleVar(value=0)
        self.scale = ttk.Scale(row_seek, from_=0, to=1, variable=self.seek_var,
                               command=self._on_seek, takefocus=False)
        self.scale.pack(fill="x")
        self.scale.bind("<ButtonPress-1>",
                        lambda e: setattr(self.viewer, "dragging", True), add="+")
        self.scale.bind("<ButtonRelease-1>",
                        lambda e: self.viewer.end_drag(), add="+")

    def _bind_keys(self):
        super()._bind_keys()
        self.root.bind("<space>", self.viewer.toggle_play)

    def _on_seek(self, value):
        if not self._ui and self.viewer.cap:
            self.viewer.seek(int(float(value)))

    def update_progress(self, cur, n, fps):
        if n != self._n:
            self._n = n
            self.scale.config(to=max(1, n - 1))
        if not self.viewer.dragging:
            self._ui = True
            self.seek_var.set(cur)
            self._ui = False
        self.lbl_time.config(text=f"{_fmt(cur / fps)} / {_fmt(n / fps)}")

    def update_play_state(self, playing):
        self.btn_play.config(text="Pause" if playing else "Play")
