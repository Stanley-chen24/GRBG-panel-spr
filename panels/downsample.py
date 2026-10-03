import numpy as np

def _place_bayer(source, m, n):
    out = np.zeros((m, n, 3), dtype=np.float32)
    out[0:m:2, 1:n:2, 0] = source[0:m:2, 1:n:2, 0]        # red
    out[0:m:2, 0:n:2, 1] = source[0:m:2, 0:n:2, 1] / 2    # green
    out[1:m:2, 1:n:2, 1] = source[1:m:2, 1:n:2, 1] / 2
    out[1:m:2, 0:n:2, 2] = source[1:m:2, 0:n:2, 2]        # blue
    return out

def dsd(arr):
   
    arr = np.float32(arr)
    m, n, _ = arr.shape
    m, n = m // 2 * 2, n // 2 * 2
    return _place_bayer(arr, m, n)

def dpd(arr):
    arr = np.float32(arr)
    m, n, _ = arr.shape
    m, n = m // 2 * 2, n // 2 * 2

    out = np.zeros((m, n, 3), dtype=np.float32)
    block = arr[0:m:2, 0:n:2, :]      

    out[0:m:2, 1:n:2, :] = block       # r
    out[0:m:2, 0:n:2, :] = block / 2   # g1
    out[1:m:2, 1:n:2, :] = block / 2   # g2
    out[1:m:2, 0:n:2, :] = block       # b
    return out
