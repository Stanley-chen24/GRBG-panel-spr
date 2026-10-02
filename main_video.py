"""影片版入口：DPI 設定、建視窗、接線、mainloop。

視窗邏輯在 gui_video.py (VideoViewer / VideoControlPanel)。
"""

import ctypes
import platform
import tkinter as tk

from gui_video import VideoViewer, VideoControlPanel


def main():
    if platform.system() == "Windows":
        try:                # >= Win 8.1
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:   # <= Win 8.0
            ctypes.windll.user32.SetProcessDPIAware()

    root = tk.Tk()
    root.title("Video Viewer")
    root.geometry("800x600")
    root.configure(bg="black")
    viewer = VideoViewer(root)

    ctrl_win = tk.Toplevel(root)
    ctrl_win.title("Controls")
    ctrl_win.geometry("800x600")
    ctrl_win.resizable(False, False)
    ctrl = VideoControlPanel(ctrl_win, viewer)

    viewer.on_image_changed = ctrl.update_thumbnail
    viewer.on_progress = ctrl.update_progress
    viewer.on_play_state = ctrl.update_play_state
    root.protocol("WM_DELETE_WINDOW", viewer.quit_app)
    ctrl_win.protocol("WM_DELETE_WINDOW", viewer.quit_app)

    root.mainloop()


if __name__ == "__main__":
    main()
