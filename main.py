"""入口：只做 DPI 設定、建視窗、接線、mainloop。

實際的視窗邏輯在 gui.py (ImageViewer / ControlPanel)
SPR 演算法在 panels/lextar_121.py。
"""

import ctypes
import platform
import tkinter as tk

from gui import ImageViewer, ControlPanel


def main():
    if platform.system() == "Windows":
        try:                # >= Win 8.1
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:   # <= Win 8.0
            ctypes.windll.user32.SetProcessDPIAware()

    root = tk.Tk()
    root.title("Image Viewer")
    root.geometry("800x600")
    root.configure(bg="black")
    viewer = ImageViewer(root)

    ctrl_win = tk.Toplevel(root)
    ctrl_win.title("Controls")
    CTRL_W, CTRL_H = 800, 600
    ctrl_win.geometry(f"{CTRL_W}x{CTRL_H}")
    ctrl_win.resizable(False, False)
    ctrl = ControlPanel(ctrl_win, viewer)

    viewer.on_image_changed = ctrl.update_thumbnail
    root.protocol("WM_DELETE_WINDOW", viewer.quit_app)
    ctrl_win.protocol("WM_DELETE_WINDOW", viewer.quit_app)

    root.mainloop()


if __name__ == "__main__":
    main()
