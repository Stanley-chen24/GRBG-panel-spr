# Lextar SPR Viewer

把圖片 / 影片經過 SPR 處理後，送到 Lextar GRBG (1:2:1) 面板上顯示的小工具。
面板接在電腦上當作第二螢幕，程式把處理好的訊號送到面板上。

## 安裝與執行

```bash
conda activate your_env # 可切換成習慣的虛擬環境 (如venv)
pip install -r requirements.txt # 需要的套件
python main.py        # 圖片版
python main_video.py  # 影片版
```

## 操作步驟

1. 面板接上電腦，`Win+P` 選「延伸」。
2. 執行程式，會開兩個視窗：顯示視窗 (黑底) 與 Controls 控制視窗。
3. `Load Images` / `Load Videos` 載入檔案，右側會出現原圖預覽。
4. `Panel Type` 選 `Lextar`，再選 SPR 演算法 (DPD / DSD / MMSE)。
5. 按 `Second Screen`，顯示視窗會移到面板上並佔滿。
6. `Previous` / `Next` 換下一個檔案；要比較兩種演算法可選取 `Side-by-side compare`。

測試建議都使用 240x240 大小的圖片 / 影片。這是由於面板解析度為 480x360


| 按鍵 | 功能 |
|---|---|
| `←` / `→` | 上一個 / 下一個檔案 |
| `F` | 切換全螢幕 (`Exit Fullscreen` 按鈕則只退出) |
| `Space` | 播放 / 暫停 (影片版) |
| `Esc` | 結束程式 |

`Panel Type` 選 `regular` 時不做任何處理，原圖直接送出，給一般螢幕用。

## 訊號是怎麼送到面板的

```
輸入 RGB (H, W, 3)
   │  spr_algorithm()      決定每個 sub-pixel 要亮多少
   ▼
out_spr (H, W, 3)          只有 sub-pixel 位置有值，其餘為 0
   │  convert_to_panel()   把值搬到面板訊號的位置
   ▼
面板訊號 (H/2, W, 3)        
```

## ConvertToPanel() 

位於 `panels/lextar_121.py`，負責把 out_spr 搬成面板訊號，並送給面板的 DDIC。

輸入 out_spr 的每個 2x2 區塊，值放在固定位置 (out_spr 位置規則)：

| | 偶數欄 | 奇數欄 |
|---|---|---|
| 偶數列 | G (值已 ÷2) | R |
| 奇數列 | B | G (值已 ÷2) |

輸出時每個 2x2 區塊併成「一列、兩個 pixel」，所以高度變一半、寬度不變 (240x240 -> 寬 240 x 高 120)：

| | 左 pixel | 右 pixel |
|---|---|---|
| R | 區塊的 R | 同左 |
| G | 上面那個 G ×2 | 下面那個 G ×2 |
| B | 區塊的 B | 同左 |

**記得 G 要先 ÷2 (SPR 階段) 再 ×2 (convert_to_panel)，兩者要成對**；只做其中一個，G 會減半或變兩倍。

## 檔案

```
main.py / gui.py              圖片版：入口 / 視窗與控制邏輯
main_video.py / gui_video.py  影片版：繼承圖片版，多了播放與時間軸
panels/lextar_121.py          spr_algorithm()、mmse()、convert_to_panel()
panels/downsample.py          DSD、DPD、_place_bayer()
filters/mmse/                 MMSE 的濾波器 (.npy)
```

**MMSE 的 filter**

- 有提供 3x3 / 15x15 兩種大小去選擇 (只是計算時取了中心為多少的範圍作為真正使用的 filter)。
- 可在 `panels/lextar_121.py` 的 `_HRB_PATH` / `_HG_PATH` 替換 filter，目前使用 3x3。


## 若要更新自己的SPR演算法上去
- 要新增 SPR 演算法：在 `gui.py` 的 `ALGORITHMS` 加名稱，並在 `spr_algorithm()` 加一個分支，輸出符合上面的 out_spr 位置規則即可。
