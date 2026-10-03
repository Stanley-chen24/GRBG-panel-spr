"""MMSE SPR 整體流程示範:
    1. H_interp (K_RB / K_G) -> 推導 H filter (Hrb / Hg)，存成 .npy
    2. H filter -> 顯示器訊號 (GRBG mosaic)，存成 panel.png
    3. 顯示器訊號 -> 模擬人眼看到的 virtual image，存成 virtual_img.png

用法：
    python mmse_spr_demo.py                      # 跳出視窗選圖，預設是儲存filter 15x15
    python mmse_spr_demo.py X.png --size X   # 指定圖片與 filter 大小

輸出到本檔旁的 result_mmse/<影像名>/<k>x<k>/。
"""

import math
import os
import sys

import cv2
import numpy as np
from PIL import Image

INPUT_SIZE = 240        
GRID = 64               # filter 計算時的網格大小
_HERE = os.path.dirname(os.path.abspath(__file__))
OUT_ROOT = os.path.join(_HERE, "result_mmse")

# H_interp
K_RB = np.array([[.25, .5, .25],
                 [.5, 1., .5],
                 [.25, .5, .25]])
K_G = np.array([[0., .25, 0.],
                [.25, 1., .25],
                [0., .25, 0.]])

# GRBG 位置
OFF_R, OFF_B, OFF_GA, OFF_GB = (0, 1), (1, 0), (0, 0), (1, 1)

# LSF：模擬顯示器點亮後對應到人眼看到的 virtual image 
LSF_SIGMA = math.sqrt(1.0 / (2.0 * math.log(2.0)))   # 0.8493218
LSF_GAIN = np.array([4.0, 2.0, 4.0]) 

def srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92,
                    ((c + 0.055) / 1.055) ** 2.4).astype(np.float32)

def linear_to_srgb(c):
    return np.where(c <= 0.0031308, c * 12.92,
                    1.055 * np.power(c, 1 / 2.4) - 0.055).astype(np.float32)

def _forward_operator(offsets, K):
    r = K.shape[0] // 2
    stamp = np.zeros((GRID, GRID))
    stamp[:K.shape[0], :K.shape[1]] = K
    stamp = np.roll(stamp, (-r, -r), axis=(0, 1))       
    cols = [np.roll(stamp, (2 * i + orr, 2 * j + occ), axis=(0, 1)).ravel()
            for orr, occ in offsets
            for i in range(GRID // 2) for j in range(GRID // 2)]
    return np.array(cols).T

def derive_filter(offsets, K, k):
    """算出網格中央那個 sub-pixel 的權重，裁成 kxk 並歸一化。"""
    A = _forward_operator(offsets, K)
    c = GRID // 4                                      # central pixel index
    e = np.zeros(A.shape[1])
    e[c * (GRID // 2) + c] = 1.0
    h = (A @ np.linalg.solve(A.T @ A, e)).reshape(GRID, GRID)

    pr, pc = 2 * c + offsets[0][0], 2 * c + offsets[0][1]
    h = h[pr - k // 2:pr + k // 2 + 1, pc - k // 2:pc + k // 2 + 1]
    return (h / h.sum()).astype(np.float32)

def compute_panel_signal(img255, hrb, hg):
    """整張圖濾波 -> clip -> 在 GRBG 位置取值，得到每個 sub-pixel 的驅動值。"""
    x = srgb_to_linear(img255 / 255.0)
    d = np.stack([cv2.filter2D(x[..., c], -1, h)
                  for c, h in ((0, hrb), (1, hg), (2, hrb))], axis=-1)
    d = linear_to_srgb(np.clip(d, 0.0, 1.0)) * 255.0

    panel = np.zeros_like(d)                              
    panel[0::2, 0::2, 1] = d[0::2, 0::2, 1]               # G1
    panel[0::2, 1::2, 0] = d[0::2, 1::2, 0]               # R
    panel[1::2, 0::2, 2] = d[1::2, 0::2, 2]               # B
    panel[1::2, 1::2, 1] = d[1::2, 1::2, 1]               # G2
    return np.uint8(np.clip(panel, 0, 255))

def virtual_image(panel):

    ax = np.arange(3) - 1.0
    xx, yy = np.meshgrid(ax, ax)
    lsf = np.exp(-(xx ** 2 + yy ** 2) / (2 * LSF_SIGMA ** 2))
    lsf = (lsf / lsf.sum()).astype(np.float32)

    lin = srgb_to_linear(panel.astype(np.float32) / 255.0)
    v = np.stack([cv2.filter2D(lin[..., c], -1, lsf, borderType=cv2.BORDER_REFLECT_101)
                  * LSF_GAIN[c] for c in range(3)], axis=-1)
    v = linear_to_srgb(np.clip(v, 0.0, 1.0))
    return np.uint8(np.clip(np.rint(v * 255), 0, 255))

# 選圖
def _pick_image():
    import tkinter as tk
    import tkinter.filedialog as filedialog
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askopenfilename(
        title="Select Image",
        filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff")])
    root.destroy()
    return path

def main(path, k):
    img = Image.open(path).convert("RGB")
    if img.size != (INPUT_SIZE, INPUT_SIZE):
        img = img.resize((INPUT_SIZE, INPUT_SIZE), Image.LANCZOS)
    img255 = np.asarray(img, dtype=np.float32)

    out_dir = os.path.join(OUT_ROOT, os.path.splitext(os.path.basename(path))[0], f"{k}x{k}")
    os.makedirs(out_dir, exist_ok=True)

    # 1. 推導 filter
    hrb = derive_filter([OFF_R], K_RB, k)              # B 與 R 同一個 filter
    hg = derive_filter([OFF_GA, OFF_GB], K_G, k)
    print(f"[1] H filter {k}x{k}")
    for name, h in (("Hrb", hrb), ("Hg", hg)):
        np.save(os.path.join(out_dir, f"{name}_{k}x{k}.npy"), h)
        print(f"    {name}_{k}x{k}.npy  sum = {h.sum():.6f}")

    # 2. 顯示器訊號
    panel = compute_panel_signal(img255, hrb, hg)
    Image.fromarray(panel).save(os.path.join(out_dir, "panel.png"))
    print(f"[2] panel.png        GRBG mosaic {panel.shape[1]}x{panel.shape[0]}")

    # 3. virtual image
    v = virtual_image(panel)
    Image.fromarray(v).save(os.path.join(out_dir, "virtual_img.png"))
    rms = np.sqrt(np.mean((v.astype(float) - img255) ** 2))
    print(f"[3] virtual_img.png  與輸入的 RMS 誤差 = {rms:.2f} (碼值)")
    print(f"輸出 -> {out_dir}")


if __name__ == "__main__":
    args = sys.argv[1:]
    size = 15
    if "--size" in args:
        i = args.index("--size")
        size = int(args[i + 1])
        del args[i:i + 2]
    if size % 2 == 0 or not 1 <= size <= GRID - 3:
        sys.exit(f"--size 需為 1~{GRID - 3} 的奇數")
    src = args[0] if args else _pick_image()
    if not src:
        sys.exit("沒有選擇影像")
    main(src, size)
