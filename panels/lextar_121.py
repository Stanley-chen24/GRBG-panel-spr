"""Lextar 1:2:1 panel 的 SPR 處理管線。

只管「輸入一張 RGB 影像，輸出面板要吃的訊號」

流程：
    raw RGB --(spr_algorithm)--> out_spr --(convert_to_panel)--> out_panel
"""

import os

import cv2
import numpy as np

from panels import downsample

_MMSE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "filters", "mmse")
_HRB_PATH = os.path.join(_MMSE_DIR, "Hrb_3x3.npy")
_HG_PATH = os.path.join(_MMSE_DIR, "Hg_3x3.npy")
_HRB = np.load(_HRB_PATH).astype(np.float32)
_HG = np.load(_HG_PATH).astype(np.float32)
MMSE_DOMAIN = "linear"


def _srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92,
                    ((c + 0.055) / 1.055) ** 2.4).astype(np.float32)


def _linear_to_srgb(c):
    return np.where(c <= 0.0031308, c * 12.92,
                    1.055 * np.power(c, 1 / 2.4) - 0.055).astype(np.float32)


def mmse(arr, domain=None):

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
    if algo_name == "DPD":
        return downsample.dpd(arr)
    if algo_name == "MMSE":
        return mmse(arr)
    return downsample.dsd(arr)  # 預設 / "DSD"

def convert_to_panel(out_spr):
    """ 輸出給 Lextar panel 的固定格式 """
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
