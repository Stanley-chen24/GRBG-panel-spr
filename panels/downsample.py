"""DSD / DPD：兩種「純下採樣」的 SPR 方法，給 121 panel 用。

都不做任何濾波/內插混色，只是「選值」，輸出跟輸入同尺寸的 sparse
array，值只填在 121 panel 的 Bayer 型 R/G/B sub-pixel 位置 (跟
panels/lextar_121.py 的 convert_to_panel() 預期的格式一致)，其餘
位置留 0——這個位置佈局是固定的，不管哪種演算法都要填在同樣的
地方，convert_to_panel() 才知道怎麼把值搬到面板訊號上。

  DSD  (Direct Subpixel-based Downsampling)
      每個 sub-pixel 位置，直接取輸入影像「同位置、同顏色通道」的值
      (R/G/B 各自獨立取自己位置的來源)。

  DPD  (Direct Pixel Duplication)
      每個 2x2 區塊只用「左上角那一個像素」當代表，把它的 R/G/B 值
      複製到該區塊四個 sub-pixel 位置 (跟 DSD 不同：DSD 是 R/G/B 各自
      取自己位置的來源，DPD 是整個區塊共用同一個來源像素)。
"""

import numpy as np


def _place_bayer(source, m, n):
    """把 source (>=m x >=n x 3 float32) 的值，依 121 panel 的 Bayer
    sub-pixel 佈局，篩進跟輸入同尺寸的 sparse array (其餘位置留 0)。

    這段位置規則 dsd() 與 mmse() 共用：差別只在
    「篩選之前，先怎麼處理來源影像」，篩到哪個位置不會變。
    """
    out = np.zeros((m, n, 3), dtype=np.float32)
    out[0:m:2, 1:n:2, 0] = source[0:m:2, 1:n:2, 0]        # red
    out[0:m:2, 0:n:2, 1] = source[0:m:2, 0:n:2, 1] / 2    # green
    out[1:m:2, 1:n:2, 1] = source[1:m:2, 1:n:2, 1] / 2
    out[1:m:2, 0:n:2, 2] = source[1:m:2, 0:n:2, 2]        # blue
    return out


def dsd(arr):
    """直接下採樣：每個 sub-pixel 位置取輸入影像同位置同色的值。"""
    arr = np.float32(arr)
    m, n, _ = arr.shape
    m, n = m // 2 * 2, n // 2 * 2
    return _place_bayer(arr, m, n)


def dpd(arr):
    """區塊下採樣：每個 2x2 區塊共用左上角那個像素的值，分配到該區塊
    的四個 sub-pixel 位置 (R 位置只會被讀到 R 通道、G 位置讀到 G 通道...
    依 convert_to_panel() 的規則，這裡直接整包 RGB 複製)。"""
    arr = np.float32(arr)
    m, n, _ = arr.shape
    m, n = m // 2 * 2, n // 2 * 2

    out = np.zeros((m, n, 3), dtype=np.float32)
    block = arr[0:m:2, 0:n:2, :]      # 每個 2x2 區塊的代表像素 (左上角)

    out[0:m:2, 1:n:2, :] = block       # red 位置
    out[0:m:2, 0:n:2, :] = block / 2   # green 位置 #1
    out[1:m:2, 1:n:2, :] = block / 2   # green 位置 #2
    out[1:m:2, 0:n:2, :] = block       # blue 位置

    return out
