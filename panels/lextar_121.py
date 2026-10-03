"""Lextar 1:2:1 panel 的 SPR 處理管線。

只管「輸入一張 RGB 影像，輸出面板要吃的訊號」

流程：
    raw RGB --(spr_algorithm)--> out_spr --(convert_to_panel)--> out_panel
"""

import os

import cv2
import numpy as np

from panels import downsample

# --- RGB-MMSE (Fang et al.，無約束 + clip) 的固定濾波器 ------------------
# 最佳解 r = (A^T A)^-1 A^T L 在取樣格點上是空間不變的，所以等於「整張圖
# 濾波一次，再在 Bayer 位置取值」。
# Hrb 給 R/B、Hg 給 G，皆以取樣點為中心、總和 = 1、上下左右對稱。
# 由前向算子 K_RB=[.25 .5 .25;.5 1 .5;.25 .5 .25]、K_G=[0 .25 0;.25 1 .25;0 .25 0]
# 精確求出後取中央再歸一化 (含負瓣；裁得越小越偏離最佳解)。
#
# 有提供兩種大小的 filter 去選擇 (在程式中替換)。
# 要換濾波器大小，只要改下面兩個檔名 (大小需為奇數，兩個檔案要成對)：
#   3x3   : Hrb_3x3.npy   / Hg_3x3.npy     <- 目前使用 (刻意縮小，當作較差的對照組)
#   15x15 : Hrb_15x15.npy / Hg_15x15.npy   (接近完整 MMSE)
_MMSE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "filters", "mmse")
_HRB_PATH = os.path.join(_MMSE_DIR, "Hrb_3x3.npy")
_HG_PATH = os.path.join(_MMSE_DIR, "Hg_3x3.npy")
_HRB = np.load(_HRB_PATH).astype(np.float32)
_HG = np.load(_HG_PATH).astype(np.float32)

# 求解域：濾波在哪個域做。"linear" 與評估器 / 面板的物理一致 (光在 linear
# 域相加)；"gamma" 直接對 code value 濾波 (較快，但會帶綠偏)。
# 濾波器與域無關，兩個域共用同一組 .npy，只差濾波前後有沒有轉換。
MMSE_DOMAIN = "linear"


def _srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92,
                    ((c + 0.055) / 1.055) ** 2.4).astype(np.float32)


def _linear_to_srgb(c):
    return np.where(c <= 0.0031308, c * 12.92,
                    1.055 * np.power(c, 1 / 2.4) - 0.055).astype(np.float32)


def mmse(arr, domain=None):
    """RGB-MMSE：整張圖濾波 -> clip -> 在 Bayer 位置取值 (out_spr)。

    步驟 (順序有意義)：
      1. code value 0..255 -> [0,1]；linear 域再轉成 linear light。
      2. R/B 用 Hrb、G 用 Hg 做 filter2D (鏡射邊界，同 baseline 的
         a_mode=mirror)。
      3. clip 到 [0,1]：就是論文的「無約束 + clip」，不做任何補償。
      4. linear 域轉回 sRGB code value，再 x255。
      5. `_place_bayer` 取 Bayer 位置，並在 **code value 域** 把 G 除以 2。
         G 的 /2 一定要在第 4 步之後：convert_to_panel() 會在 code value 域
         乘回 2，兩者互為反運算，G 才會原封不動送到面板。若在 linear 域
         除以 2 再編碼，convert_to_panel 乘回 2 後 G 就不等於 D_G 了。
    """
    domain = domain or MMSE_DOMAIN
    arr = np.float32(arr)
    m, n, _ = arr.shape
    m, n = m // 2 * 2, n // 2 * 2
    x = np.clip(arr[:m, :n] / 255.0, 0.0, 1.0)
    if domain == "linear":
        x = _srgb_to_linear(x)

    d = np.empty_like(x)
    d[..., 0] = cv2.filter2D(x[..., 0], -1, _HRB)
    d[..., 1] = cv2.filter2D(x[..., 1], -1, _HG)
    d[..., 2] = cv2.filter2D(x[..., 2], -1, _HRB)
    d = np.clip(d, 0.0, 1.0)

    if domain == "linear":
        d = _linear_to_srgb(d)
    return downsample._place_bayer(d * 255.0, m, n)


def spr_algorithm(arr, algo_name=None):
    """SPR 演算法本體：raw RGB -> sub-pixel 取樣值 (out_spr)。

    這是唯一真正用到 SPR filter/kernel 的地方。algo_name 由 GUI 帶入
    (單張顯示與 side-by-side 都會指定)；不帶時預設用 DSD。

    目前已實作 DSD / DPD (見 panels/downsample.py，純下採樣、無濾波)，
    以及 MMSE (本檔的 mmse()，固定濾波器 + 取樣)。
    """
    if algo_name == "DPD":
        return downsample.dpd(arr)
    if algo_name == "MMSE":
        return mmse(arr)
    return downsample.dsd(arr)  # 預設 / "DSD"


def convert_to_panel(out_spr):
    """121 panel 固定的 sub-pixel 幾何搬移 (與 SPR 演算法無關)。
    """
    m, n, chan = out_spr.shape
    m, n = m // 2 * 2, n // 2 * 2
    panel = np.zeros((m // 2, n, chan), dtype=np.float32)

    # red
    panel[:, 0:n:2, 0] = out_spr[0:m:2, 1:n:2, 0]
    panel[:, 1:n:2, 0] = out_spr[0:m:2, 1:n:2, 0]
    # green
    panel[:, 0:n:2, 1] = out_spr[0:m:2, 0:n:2, 1] * 2
    panel[:, 1:n:2, 1] = out_spr[1:m:2, 1:n:2, 1] * 2
    # blue
    panel[:, 0:n:2, 2] = out_spr[1:m:2, 0:n:2, 2]
    panel[:, 1:n:2, 2] = out_spr[1:m:2, 0:n:2, 2]

    return np.uint8(np.clip(panel, 0, 255))
