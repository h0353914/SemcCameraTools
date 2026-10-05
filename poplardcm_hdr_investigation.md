# poplardcm（SO-01K / msm8998）HDR 顯示調查紀錄

最後更新：2026-10-06　測試機：r11（QV700WMR11）、BH904ULGAT，LineageOS 22.2 / Android 15

> 文件位置：`/home/h/tmp/SemcCameraUI/poplardcm_hdr_investigation.md`（提交紀錄見第 8 節）。
> 標示「推測」的是沒有直接證據的判斷。第 2～4 節是原因分析與調查歷史；**目前的做法與狀態以第 1、5～9 節為準**。

---

## 1. 結論（一頁版）

| 問題 | 結論 |
|---|---|
| 面板與顯示硬體支援 HDR 嗎？ | 支援。面板 700 nits，顯示引擎有 `hdr` 功能，HEVC Main10 HDR10 可硬體解碼 |
| 為什麼原本 HDR 顯示不對？ | 原廠 HDR 做在 Sony 改過的 HWC，LineageOS 沒有這套（第 3 節）。核心自己切到 `hal_hdr` 時，**QDCM 校正檔缺 Virtual PCC → HDR 產生器 `Failed getting the Virtual PCC` → forward LUT 全零**（4.6 實機 A/B） |
| 目前怎麼解？ | **硬體 HDR 路徑**：校正檔加入含 Virtual PCC 的 `hal_hdr` 模式、讓核心產生 3D LUT、HWC 開寬色域（第 5 節）。不修改任何預編譯 SO |
| 實機結果？ | r11 與 BH904ULGAT 播 HEVC HDR10：圖層 dataspace `BT2020_ITU_PQ`、核心切到 `hal_hdr`、**沒有** `Invalid Lut Entries`／ToneMapper 錯誤；使用者目視兩台畫面正常、沒有全黑（第 6 節） |
| 舊版 ROM 的卡幀？ | BH904ULGAT 舊版（`sdm.disable_hdr_lut_gen=1`）每幀 tone mapper 失敗 2078 次；刷新版後降為 0 |
| YouTube 的 HDR？ | 與顯示 HDR 路徑**無關**：`334`（720p VP9.2）走 YouTube 內建 libvpx 軟體解碼＋自己的 GL 轉成 SDR，原廠機也一樣；偶發綠屏／卡住與顯示設定無關（第 7 節） |
| 還沒驗證的 | 面板實際亮度（nits）與色彩準確度；DSPP 暫存器無法直接讀（第 6 節） |

---

## 2. 元件與位置

### 2.1 實際在手機上執行的顯示元件

| 元件 | 來源 | 位置（專案內） | 備註 |
|---|---|---|---|
| `hwcomposer.qcom.so` | **從原始碼編譯** | `hardware/qcom-caf/msm8998/display/sdm/libs/hwc2/` | 唯一可改的 HWC 層 |
| `libsdmcore.so`（64 位元） | **Sony 預編譯檔** | `vendor/sony/yoshino-common/proprietary/vendor/lib64/libsdmcore.so` | `Android.bp` 是 `cc_prebuilt_library_shared`；`sdm/libs/core/` 的原始碼只編 32 位元，**改了對手機無效** |
| `libsdmextension.so` | 預編譯 | 同上目錄 | 決定哪些圖層要色調映射、產生 3D 對照表（`MarkLayersForToneMap`、`Generate3DLut`） |
| `libsdm-color.so` | 預編譯 | 同上目錄 | QDCM 色彩管理，讀校正檔 |
| `libhdr_tm.so` | 預編譯 | 同上目錄 | Qualcomm 色調映射函式庫 |
| `libsdm-disp-vndapis.so` | 預編譯 | 同上目錄 | LiveDisplay 走的 QDCM API |
| QDCM 校正檔 | 原廠＋提取修補 | `vendor/sony/poplardcm/proprietary/vendor/etc/qdcm_calib_data_{6,9}.xml` | 原廠 SO-01K 47.2.B.5.38 檔案經 `extract-files.py` 的 blob_fixup 加入 `hal_hdr` 模式（55→56 個模式）；面板代號 9 → `_9` |
| 顯示核心驅動 | 開源 | `kernel/sony/msm8998/drivers/video/fbdev/msm/` | `mdss_mdp.c`、`mdss_dsi_panel.c`、`mdss_fb.c` |
| 面板 dts | 開源 | `kernel/sony/msm8998/arch/arm/boot/dts/qcom/dsi-panel-poplar*.dtsi` | 含 `qcom,mdss-dsi-panel-hdr-enabled`、峰值亮度等 |
| 解碼器（OMX） | 開源 | `hardware/qcom-caf/msm8998/media/mm-video-v4l2/vidc/vdec/` | |
| Venus 韌體 | 原廠 | 手機 `/vendor/firmware_mnt/image/venus.*` | |
| LiveDisplay | 開源 | `hardware/lineage/livedisplay/sdm/` | 透過 `vendor.lineage.livedisplay.IDisplayModes` 切 QDCM 模式 |

### 2.2 原廠（SO-01K）HDR 實作位置

來源：`/mnt/f/Android/xz1/rom_o/SO-01K_NTT DoCoMo JP_47.2.B.5.38-R12C/vendor_X-FLASH-ALL-99C3.sin`

| 項目 | 說明 |
|---|---|
| `vendor/lib64/hw/hwcomposer.msm8998.so` | Sony 改過的 HWC。符號：`InitHdrConfigSomc`、`FillGpuLutSomc`、`GetGpuLutTypeSomc`、`PrepareSomc`、`ChooseHdrModeForBrightness` |
| `vendor/etc/br2tm.xml` | 亮度 100～700 nits 對應 QDCM 模式 `SMH0_10`～`SMH0_70`（HDR10）、`SMHG_*`（HLG） |
| `vendor/etc/tminv_dat01`～`03` | 各 29478 位元組，3 個平面 × 17³ 個 uint16（低 10 位元有效），依序是 HDR10、HLG、HLG+HDR10 並存（載入順序推斷，未完全證實） |
| 屬性 | 原廠設 `vendor.display.disable_hdr_lut_gen=1`；另有 `somc.hdr.mode`、`somc.hdr.adaptlumi.disable` |
| 暫存備份 | `SemcCameraUI/.tmp/stock/hdr/`（`br2tm.xml`、`tminv_dat01～03`、原廠 `hwcomposer.msm8998.so`） |

---

## 3. 病根（為什麼 HDR 顯示不對）

### 3.1 顯示系統「宣告支援 HDR」的來源

1. 面板 dts 的 `qcom,mdss-dsi-panel-hdr-enabled`（poplar 三個面板各一行）。
2. 核心 `mdss_mdp.c` 的 `MDSS_QUIRK_HDR_SUPPORT_ENABLED`（在 MDP 硬體版本 300/301 區塊）。
3. 原廠 `libsdmcore.so` 的 `DisplayBase::GetConfig`：`hdr_supported` 只取決於硬體能力，**不看面板旗標**（反組譯確認），所以光拿掉 dts 的旗標沒有效果（quxng 的 1f21cfca 在這台無效）。
4. HWC 的 `GetHdrCapabilities` 回報 HDR10 → SurfaceFlinger 看到 `hdr10=true`。

### 3.2 宣告 HDR 之後的三個問題

| # | 問題 | 位置 | 證據 |
|---|---|---|---|
| A | HWC 看不到「這是 BT2020/PQ」 | `hwc_layers.cpp` 的色彩轉換被 `FEATURE_WIDE_COLOR` 包住，而 `TARGET_HAS_WIDE_COLOR_DISPLAY` 沒設 | 顯示圖層表的色彩欄位全是 6（BT601）；開啟後影片層變成 9（BT2020） |
| B | 核心把 **UI 反向轉成 PQ**（SDR→HDR），但面板沒進 PQ 解碼模式 | `libsdmcore`／`libsdmextension`（預編譯） | 傾印量測：UI 白 255→172、128→123、32→67（見 4.2） |
| C | 核心自己切到 `hal_hdr` 色彩模式 → **全黑** | `libsdmcore.so` `DisplayBase::HandleHDR` → `libsdm-color.so` | 見第 4 節 |

### 3.3 其他已確認的事實

- QDCM 校正檔本來就**沒有** `hal_hdr` 這個模式（只有 `hal_native`），所以不加模式時核心會報 `Unknown Mode : hal_hdr` 並放棄。
- 校正檔裡的 `SMH0_10`～`SMH0_70` 共 25 個模式（`SMHG_*` 是 HLG 版本）就是原廠的**面板 PQ 解碼曲線**：SDR 模式的 3D 對照表是一比一，`SMH0_31` 在 985 nits 時輸出約 3871/4092，約 1000 nits 接近全亮。
- `sdm.disable_hdr_lut_gen`：`libsdmextension.so` 讀這個名字；`libsdmcore.so` 讀 `vendor.display.disable_hdr_lut_gen`。專案 `system.prop` 原本設了 `sdm.` 那個，會讓核心不產生對照表，HWC 的色調映射就每幀報 `Invalid Lut Entries`（BH904ULGAT 舊版 ROM 實測 2078 筆，造成卡幀）；現已移除（見第 5 節）。
- `poplardcm/system.prop` 的 `sys.hwc_disable_hdr=1` 是**舊名稱，沒有作用**（HWC 讀的是 `vendor.display.hwc_disable_hdr`）。
- 硬體解碼：HEVC Main10 / Main10 HDR10 可用；**VP9 只有 Profile 0**（OMX 原始碼對 VP9 的 profile 查詢直接回「沒有更多」，且 Venus 韌體字串有 `422/444 and >8 bitdepth not supported`，實測 Profile 2 回 `Unsupported input stream 0x80000005`）。
- 顯示核心的這幾個預編譯檔來自 **mermaid（Xperia 10 Plus）**，md5 與 SO-01K 原廠版本都不同。

---

## 4. 全黑問題的調查（歷史紀錄）

> 本節與 4.4～4.7 記錄的是 2026-10-03 當時的調查過程與測試條件（臨時核心 #60、手動改 `build.prop` 等），**不是目前的系統狀態**。最後的結論與目前實作見第 1、5 節。

### 4.1 對照表（這是定位的主要依據）

| 情況 | 畫面 |
|---|---|
| 核心**不**切模式（`vendor.display.disable_hdr_lut_gen=1`） | 有畫面、偏灰 |
| 核心不切，改用 **LiveDisplay 切到 `hal_hdr`** | **變亮、有畫面**（正確的 HDR 效果） |
| 核心自己切到 `hal_hdr` | **全黑** |
| 核心切到「與預設模式 101 位元組完全相同的複製品」（附加在最後，ModeID 200 或 50） | 全黑 |
| `SMH0_31` 在原位置就地改名成 `hal_hdr` | 全黑 |
| `hal_hdr` 關掉畫面調整(PA)與抖動 | 全黑 |
| 在一般桌面用 LiveDisplay 切 `100_sRGB`、`SMH0_10` | 有畫面 |
| 核心切換後再用 LiveDisplay 補套用（+0.3、0.7、1、1、2 秒，共 5 次） | 全黑 |
| 核心切換後關閉閒置 GPU 退回逾時（`vendor.display.idle_time=0`） | 全黑 |
| 核心切換後手動送 `dpps:on` | 全黑 |

已排除：模式資料、Dpps、閒置逾時、背光（讀值 2109 沒變）、合成畫面（傾印顯示正常）。

### 4.2 量測

- **背光：** HDR 播放時維持 2109。
- **UI 色調映射（傾印，畫面緩衝區不壓縮）：**

  | UI 輸入灰階 | 255 | 230 | 160 | 128 | 64 | 32 |
  |---|---|---|---|---|---|---|
  | 色調映射後 | 172 | 154 | 134 | 123 | 92 | 67 |

- 搭配 `SMH0_31` 解碼後，UI 亮度相對正常的估算值：32→96%、64→65%、128→48%、160→44%、230→39%、255→55%（**推算，非實測**）。
- 色調映射的對象是**畫面緩衝區（UI）**，不是影片；影片層直接送顯示硬體。
- GPU 約 6% 忙碌是在處理 UI，**不能**當成「影片色調映射有在跑」的證據。

### 4.3 確定與不確定

- **確定：** 核心路徑與 LiveDisplay 路徑最後都進 `libsdm-color.so`，但進入函式不同（`ColorIntfSetDisplayMode` vs `DisplayAPISetActiveMode`）；只有核心路徑會在切換後立刻出現 `ColorManager::ColorIntfGetActiveColorParam: No settings available for this feature`。
- **不確定：** 錯在 `libsdm-color.so` 的函式本身，還是 `libsdmcore.so` 在畫面準備途中的呼叫時機／順序。需要反組譯這兩個檔案比對寫入 DSPP 的功能才能分辨。
- 原廠解法（`PrepareSomc`）是 Sony HWC 自己切模式、核心保持不切。

### 4.4 後續靜態反組譯（2026-10-03；pending action 判讀已於 4.5 更正）

以專案實際使用的 64 位元 mermaid 預編譯庫（`vendor/sony/yoshino-common/proprietary/vendor/lib64/`）及 SO-01K 原廠 `vendor.sin` 內的庫交叉檢查。Ghidra MCP 此次沒有啟動，因此以下是 LLVM AArch64 反組譯加上 SDM/HWC 呼叫端原始碼對照，尚未取得 Ghidra C-like 偽碼。

> **更正提醒：** 本節所稱 API pending action `0x401` 與必經 RestoreColorTransform 的結論已由 4.5 撤回；保留此段供追溯，後續判斷請以 4.5 為準。

#### 呼叫路徑已確認不同

**HDR 自動路徑：**

```
DisplayBase::HandleHDR
  → DisplayBase::SetColorModeInternal("hal_hdr")
  → ColorManagerProxy::ColorMgrSetMode(mode_id)
  → ColorIntfSetDisplayMode(&pp_features_, 0, mode_id)
  → SetDisplayMode(...)
```

`SetColorModeInternal` 先以模式名稱查 `color_mode_map_`，再把找到的 mode ID 交給 `ColorMgrSetMode`。`ColorMgrSetMode` 直接呼叫 `ColorIntfSetDisplayMode`。`HandleHDR` 在 `Prepare()` 的 `BuildLayerStackStats()` 之後、`PrePrepare()` 之前執行；成功設定模式後只呼叫 `ControlDpps(false)`，此路徑沒有另外呼叫 HWC 的 `RestoreColorTransform()`。

**LiveDisplay／QDCM API 路徑：**

```
DisplayAPISetActiveMode
  → SetDisplayMode(...)
  → PPPendingParams.action = kInvalidating | kModeSet (0x401)
  → HWCSession::QdcmCMDHandler
  → HWCDisplayPrimary::RestoreColorTransform()
  → HWCColorMode::RestoreColorTransform()
  → Display::SetColorTransform(...)
```

兩條路徑確實共用 `SetDisplayMode`，但 API 路徑成功後會回傳 pending action `0x401`；HWC 將其拆成 `kInvalidating` 和 `kModeSet`，其中 `kModeSet` 會重送 HWC 保存的色彩轉換矩陣並刷新畫面。HDR 自動路徑沒有這個後續動作。這是目前找到最明確的呼叫順序差異，應優先驗證自動 HDR 切換後 PCC／色彩轉換狀態是否仍為舊值。

#### `No settings available` 訊息的來源

mermaid `libsdm-color.so` 的 `ColorIntfGetActiveColorParam` 只處理參數 `0x95` 和 `0x97`，並分別向 `QdcmMobileCacheStorage::GetFeatureFromActiveMode(25/26)` 取目前模式的 feature。feature 查詢沒有結果時，函式會輸出 `No settings available for this feature` 並回傳錯誤碼 7；因此這行訊息表示「當下 active-mode cache 查不到該 feature」，不等同於已證明 DSPP 寫入失敗或造成黑屏。還需追查是哪個呼叫者請求 25/26，以及 `hal_hdr` 的 cache 為何沒有這些項目。

#### 目前判斷與限制

- **已證實：** 自動 HDR 模式切換和 LiveDisplay 都落到 `SetDisplayMode`，但 LiveDisplay 成功後多一個 `RestoreColorTransform()`／刷新步驟；核心自動路徑沒有。
- **待驗證假說：** 少了這個步驟可能讓色彩轉換／PCC 狀態在 HDR 進入時不同步，並與 `No settings available` 同時出現。尚無 DSPP 暫存器讀值或受控 A/B 證明它就是全黑的直接原因；PA 與抖動關閉後仍黑，也表示不能把原因簡化成這兩項。
- **仍未定位：** 哪一個具體 PP feature 或 DSPP block 被寫成導致黑屏的值；以及 `GetActiveColorParam(25/26)` 的 caller 與它對 commit 的實際影響。
- **二進位參考：** 專案內 mermaid 兩個庫的複本、SO-01K 原廠庫及逐函式反組譯暫存於 `.tmp/stock/` 和 `.tmp/mermaid_*.s`，沒有修改產品程式碼或推送手機。

---


## 4.5 Ghidra 續查：未初始化的虛擬 PCC 與 DSPP gamut 覆寫（2026-10-03）

> 本節更正 4.4 的 pending-action 判讀，並補上直接 caller。已用本機 Ghidra 12.0.4 headless 取得偽碼、用 LLVM AArch64 反組譯核對。**本節為靜態分析；手機 A/B 的實際結果見 4.6，尚不能宣稱面板黑畫面已修復。**

### 最重要的新發現

最強的原因候選已從「少做 RestoreColorTransform」移到 **`libhdr_tm.so` 缺少虛擬 PCC 時仍使用未初始化矩陣，產生的全域 3D LUT 隨後覆寫 DSPP gamut**。

兩條切模式路徑不只是共用 `SetDisplayMode`：自動路徑的 `ColorIntfSetDisplayMode` 另將 display ID 對應到核心的 `PPFeaturesConfig*`，使 HDR 產生器能寫回 PP。API 路徑的 `DisplayAPISetActiveMode` 沒有這個登記動作。這個差異能解釋為什麼完全相同的模式資料，在兩條路徑得到不同結果；是否就是當次黑畫面的完整因果鏈，仍需 A/B。

### 分析檔確實對應 r11

產品樹、分析複本及 r11 `/vendor/lib64/` 的 SHA-256 已逐項核對：

| 庫 | SHA-256 |
|---|---|
| libsdmcore.so | `2adb8b5728cd958c3d100f6ca8638eb594448040350a546ac2628c25dcb8a5a1` |
| libsdm-color.so | `42cd75cd60d790c2b16a80e651f2381d3350e58f1c572724dab4d54abad10db9` |
| libsdmextension.so | `e38f6a760c7e59418b9f586af3ebd40bf692f065ca4c056a10abb63faef2339a` |
| libhdr_tm.so | `7607aace1304f0e2abf5cfecee8c5b2a76dc1e188610a46eddd3a0eb04a4d6f0` |

注意：舊 `.tmp/stock/libsdmextension.so` 是另一版本（SHA-256 `a722f5f1…`），本輪改用產品庫複本 `.tmp/hdr_black/libsdmextension-mermaid.so`。`ro.vendor.display.hdr.config` 在 r11 為空，HDR 產生器會使用內建參數。

### 更正：mermaid API 路徑沒有回傳 0x401

`libsdm-color.so` 的 `DisplayAPISetActiveMode`（ELF VA `0x32484`）在成功時回傳：

- `this+0xf8 == 0`：pending action `0x1`（kInvalidating）。
- 否則：pending action `0x100`（kConfigureDetailedEnhancer），params 指向 PP 資料。

此函式沒有 OR `0x400` 的指令。HWC 原始碼有 `kModeSet → RestoreColorTransform()`，**不能因此推論本機 mermaid 庫真的回傳 kModeSet**。4.4 的 `0x401` 與「LiveDisplay 成功後必定重送矩陣」結論撤回。

### 確定找到的 PP 佇列登記差異

`ColorIntfSetDisplayMode`（`0x29eac`）呼叫 `SetDisplayMode` 後，把 `out_features` 存入 `this+0x10` 的樹狀 map，key 為 **display ID**，不是 mode ID；在 `0x29f90` 將指標寫入節點 `+0x28`。

`DisplayAPISetActiveMode` 只做 `SetDisplayMode` 與 pending action，不做上述登記。該 map 可能因先前自動切模式已有內容，不能假設每次 LiveDisplay 操作時一定是空的。

`ColorIntfSetActiveColorParam(0x69, display_id, payload)`（`0x2aaa0`）會查這個 map：沒有 PP 指標便回 7，訊息為 `PPOutFeatures not available for the given disp id or it is NULL`；有指標時會呼叫 `Apply3DLutFineModeFeature`／coarse，設定 PP dirty。

`Apply3DLutFeature`（`0x39040`）把資料變成 **hardware PP feature ID 6（gamut），version 9**。`AddFeature`（`0x276f8`）會刪掉同一 ID 的既有 feature 再放入新的。因此它能在同一輪 commit 前取代校正 XML 剛套用的 gamut。

### No settings available 的直接 caller 已定位

`libhdr_tm.so::HDR_playback_strategies`（`0x15c48`）在 `0x16708` 呼叫：

```text
ColorIntfGetActiveColorParam(color_manager, 0x95, 0, &virtual_pcc)
```

由實際 AArch64 x0／w1／w2／x3 核對：參數 0x95 對應 active-mode feature 25。這是直接 caller，而不是從 vendor API 名稱猜測。

另從 `libsdm-disp-vndapis.so` 確认參數語意：

| 查詢參數 | active-mode feature | 語意 |
|---|---|---|
| 0x95 | 25 | global virtual PCC |
| 0x97 | 26 | panel brightness info |

目前直接確認的 HDR 產生器 caller 請求 **25**；不能把先前同一句錯誤訊息直接歸因到 26。

### 具體缺陷：查詢失敗後仍使用未初始化矩陣

以反組譯與偽碼共同核對：

1. `0x163bc`～`0x163e8`：配置 `operator new(0x110)`，存入 TMParams `+0x1c0`。此配置不是 value-initialization，沒有清零或設定 identity。
2. TMParams `+0x24`（panel PCC enable）取輸入參數 `+4`。擴充庫 `Generate3DLut` 會對 primary display 設此旗標為 1。
3. `0x16708` 查詢 feature 25；只有成功分支 `0x1672c` 之後才把 PCC 係數複製到剛配置的矩陣。
4. 失敗分支 `0x16710`～`0x16728` 只輸出 `Failed getting the Virtual PCC` 然後繼續；沒有設定 identity、沒有關閉 panel PCC，也沒有中止 HDR 產生。
5. `lut3d_process` 在 `0x13c7c` 檢查 TMParams `+0x24`，非零便在 `0x13c8c` 呼叫 `panel_mapping_PCC`。HLG 對應呼叫點為 `0x129cc`。
6. `panel_mapping_PCC`（`0x11c20`）直接讀取 TMParams `+0x1c0` 的 double 係數，把整份 LUT 的 RGB 多項式映射後限制到 0～1。

因此，feature 25 缺失且 primary-display PCC 啟用時，**未初始化矩陣確實進入 LUT 運算**。若配置區塊恰為零，三色輸出會全為零；若含舊值／NaN，輸出依資料而異。不能把未初始化記憶體一律說成零，也尚未量到黑畫面當次的矩陣與 LUT。

### 從錯誤 LUT 到顯示硬體的完整候選鏈

```text
DisplayBase::HandleHDR
  → ColorIntfSetDisplayMode
      → 套 XML 模式
      → 登記 display 0 → PPFeaturesConfig*
  → 擴充庫 StrategyImpl::HandleHDR / Generate3DLut
      → libhdr_tm::HDR_playback_strategies
          → 讀 virtual PCC（feature 25）失敗仍繼續
          → panel_mapping_PCC 使用未初始化矩陣
          → ColorIntfSetActiveColorParam(0x69, 0, &gamut_payload)
              → Apply3DLutFineModeFeature
              → AddFeature(ID 6)，取代 XML gamut
  → ColorManagerProxy::Commit
      → HWPrimary::SetPPFeatures
          → MSMFB_MDP_PP ioctl（0xc1586d9c）
```

HDR 產生器的兩個 DSPP gamut 寫回 call 位於 `0x16b18`／`0x16eec`，x3 是 stack payload，並非 NULL。Ghidra 對匯入的 C++ 成員函式未正確還原隱含 this，原始 `hdr_tm.c` 有錯誤的參數數量及 `(void*)0`；上述參數以 `.s` 的寄存器為準，不能直接照抄偽碼。

此鏈同時能解釋：模式換成 SDR 複本仍黑、關掉 PA／dither 仍黑、背光未變、圖層傾印正常，以及只走 LiveDisplay 模式套用時有畫面。這些屬於相符的推論，尚無受控 A/B 證明。

### 已建立最小 A/B 複本，尚未推送

產物與製作腳本都在 `.tmp/hdr_black/`，只修改複本的兩條指令，沒有新增產品函式：

| 複本 | 隔離項目 | 修改 |
|---|---|---|
| `libhdr_tm-no_dspp_write.so` | 保留圖層 LUT 計算，阻止兩個全域 gamut 寫回 | `0x16b18`／`0x16eec` 的 BL 改為 `mov w0, #0` |
| `libhdr_tm-no_panel_pcc.so` | 保留 gamut 寫回，跳過未初始化 PCC 的映射 | `0x129cc`／`0x13c8c` 的 BL 改為 NOP |

`make_ab.py` 檢查來源 SHA-256、ELF executable LOAD 位址、原始指令、產物長度及修改範圍；產物亦已重新反組譯核對。這些僅供實驗，不能當正式修正。

下一輪應以可重現黑畫面的硬體 HDR 環境逐一測試：原版 → no_dspp_write → 原版 → no_panel_pcc → 原版，每次重啟 HWC，避免 map／LUT 快取殘留。A 恢復畫面可支持 gamut 覆寫是必要因素；B 也恢復可進一步支持未初始化 PCC 是來源。應同時記錄 virtual-PCC 查詢結果、forward LUT checksum、SetActiveParam 回傳碼及 feature 6 提交，並確認面板實際畫面。

本輪 r11 的 `mdp/caps` 仍沒有 `hdr`，且 `vendor.display.disable_hdr_lut_gen=1`。沒有切回硬體 HDR、沒有換庫／刷核心，故未進行上述實測。本輪僅靜態反編譯、唯讀手機檢查及離線實驗產物，未改產品程式碼，未編譯相機或執行相機功能測試。

證據：`.tmp/hdr_black/{color,core,extension,hdr_tm}.c`、同目錄 `.s`、四個 Ghidra project／analysis log、`device_state.txt`／`device_tm.txt`、`ab_hashes.txt`。Ghidra 偽碼位址有預設 image base `0x100000`，本文統一使用去除該 base 的 ELF VA。


---

## 4.6 實機受控 A/B（2026-10-03）

依使用者要求直接在 r11（QV700WMR11）實測。所有日誌與測試複本放 `.tmp/hdr_black/runtime/`，未修改產品原始碼。

### 實驗條件與有效性

每輪透過 fastboot **暫時啟動** `.tmp/ab_boot/boot.img`（核心 #60，能力列包含 `hdr`），沒有刷寫 boot 分割區。暫時將 `vendor.display.disable_hdr_lut_gen` 設為 0。以原校正 XML 的 Default／ModeID 101 完整複製成 ModeID 200、名稱 `hal_hdr`，原有 `hal_native` 為 ModeID 51；兩份 XML 均加入相同測試模式。

每輪完整開機，核對 `libhdr_tm.so` SHA-256、HDR 核心能力與屬性，再用相同 `hdr10_hevc_3m.mp4`、Glimpse 播放器啟動影片。SurfaceFlinger 均必須具備 `hdr10=true`、`BT2020_ITU_PQ` 影片層；日誌均顯示自動切到 `hal_hdr`。跳過 PCC 輪的 PQ 層另確認 `forceClientComposition=false`。

先前 `original_1`／`original_valid_*` 嘗試因 framework 重啟後又回到 #61、HDR 能力消失，**不是有效 A/B**，不能當成 HDR 證据。以下僅採 `boot_*` 完整開機測試。

### 結果

| 輪次 | 修改 | Virtual PCC | forward checksum | inverse checksum | HDR 後 gamut map_en |
|---|---|---|---:|---:|---:|
| boot_original_1 | 原版 | 取得失敗 | 0 | 7169351 | 0 |
| boot_no_dspp_write | 僅跳過兩處 LUT 寫回呼叫 | 取得失敗 | 0 | 7169351 | 2 |
| boot_no_panel_pcc | 僅跳過 PQ／HLG 的 panel_mapping_PCC 呼叫 | 取得失敗 | 28141764 | 7169351 | 0 |
| boot_original_2 | 換回原版複測 | 取得失敗 | 0 | 7169351 | 0 |

每輪 SDR 基準的 `map_en=2`。原版及跳過 PCC 輪 `SetActiveParam for 3D LUt returned = 0`；停用寫回輪這個 0 是補丁模擬成功，不能當作真的呼叫或提交成功。

**已實證的範圍：** 相同 HDR 輸入、相同模式資料下，原版遇到 `Failed getting the Virtual PCC` 後產生全零 forward LUT；僅移除 PCC 計算即產生非零值，且 inverse checksum 不變。換回原版複測也再次回到 checksum 0。這將「PCC 失敗路徑導致全零 forward LUT」從靜態推測提升為實機 A/B 支持。停用 LUT 寫回後 `map_en` 留在 2，亦支持原版寫回路徑確實改變 DSPP gamut 設定。

**尚未證明的範圍：** 使用 `MSMFB_MDP_PP`（op 8、version 9、READ）讀回 DSPP gamut，四表 RGB 均為零，連跳過 PCC 輪也是零。因此讀回尚未交叉驗證正確的 DSPP／LUT bank、有效啟用狀態及最終提交結果，不能把零值直接視為已量到面板全黑。`map_en` 是映射位元，不是 gamut 啟用位元。Android screencap 也不涵蓋 DSPP 的最終面板處理。本輪不能宣稱跳過 PCC 已修好肉眼黑畫面或顏色正確。

下一個確切工作是核對非零 forward LUT 進入 `Apply3DLutFeature`／PP commit 的資料，以及面板實際使用的 DSPP block、bank 與啟用位元；正式修正應提供符合原廠模式資料的 Virtual PCC，不能直接把本輪跳過 PCC 當產品修補。

### Virtual PCC 資料來源補查

測試前 r11 的 `qdcm_calib_data_9.xml` 共 55 個模式，只有 `ModeID=51`、`Name=hal_native` 含 `FeatureType=25`，`DataSize=272`、`Disable=1`，資料為非零係數。Default／ModeID 101 沒有 feature 25，因此本輪從 Default 複製的 hal_hdr 也沒有該資料；這是本輪缺失 PCC 的具體來源，不能推論整份原廠 XML 完全沒有 PCC。

`ColorIntfGetActiveColorParam(0x95)` 從目前模式的 feature 25 取得資料，不會搜尋 hal_native 借用；有資料時回傳狀態 `!Disable` 並複製係數。`DisplayAPISetGlobalVirtualPccConfig` 亦會經 `CacheFeature` 寫入 feature 25（0x39f04～0x39f0c），因此來源可能是模式校正資料或執行期 API 設定。本次已在 XML 找到實際係數，但尚未證明應把 Disable=1 的 hal_native 資料直接搬到 HDR 並啟用。

### 還原驗證

實驗結束後已還原原版 libhdr_tm、兩份校正 XML 與 vendor/build.prop，正常重開機回核心 #61，HDR capability 不含 hdr，vendor.display.disable_hdr_lut_gen=1，其餘兩項暫時屬性為空，/vendor 為唯讀。boot 分割區及上述四份檔案的 SHA-256 全部符合測試前備份。驗證輸出：`.tmp/hdr_black/runtime/restored.txt`。

## 4.7 保留原版 SO、只補校正資料的實測

續查 stock 校正 XML，確認原廠檔案也只有 `hal_native` 有 feature 25，無 `hal_hdr`。`qdcm_calib_data_6.xml` 與 `_9.xml` 的 PCC payload 相同。此結果配合 2.2／3.3：原廠 Sony HWC 用 `SMH0_*`／`SMHG_*` 與自身 GPU LUT，並設 `vendor.display.disable_hdr_lut_gen=1`；因此不能假設原廠 XML 原本應有供通用 Qualcomm HDR 產生器使用的 `hal_hdr`。

### 停用旗標的實際行為

getter `ColorIntfGetActiveColorParam(0x95)` 回傳 `!Disable`，但只要 feature 資料存在仍複製係數、回傳成功。`libhdr_tm` 在 `0x1670c` 只檢查函式錯誤碼；成功分支 `0x1672c`～`0x16810` 直接複製係數，沒有檢查回傳 payload 的 enabled 欄位。因此 **XML 的 Disable=1 不會阻止此 HDR 路徑使用 PCC**；不能以為必須改成 Disable=0 才能補資料。

### 原版庫資料補齊測試

建立 `.tmp/hdr_black/qdcm_{6,9}_hdr_pcc_disabled.xml`：在既有 Default 複製的測試 hal_hdr 中加入該面板 hal_native 的 feature 25，完整保留 272-byte payload 與 Disable=1，並調整 NumOfFeatures。使用未修改的 `libhdr_tm.so`，其 SHA-256 仍是 `7607aace…`。每輪開機、影片與 HDR 有效性檢查沿用 4.6。

日誌 `.tmp/hdr_black/runtime/boot_xml_pcc_disabled/phase_logcat.txt`：

- 自動 `Setting color mode = hal_hdr`。
- `Failed getting the Virtual PCC` 消失；出現 PCC index[0..2]，線性係數依序為 `(1.189716,-0.015672,-0.020894)`、`(-0.004020,0.982968,0.014787)`、`(0.002154,-0.002396,0.744202)`，吻合 XML。
- forward checksum **27244724**，inverse checksum **7169351**。
- `SetActiveParam for 3D LUt returned = 0`。

結論：**不用改 SO，只補當前模式的原有 PCC 資料，就能讓原版 HDR 產生器消除全零 forward LUT。** 這也直接驗證 PCC 的 XML → active-mode feature 25 → libhdr_tm 來源鏈。

限制：這是資料供應的受控實驗，不代表 hal_native 的 PCC 加上 Default 曲線就是原廠 HDR 模式；尚未驗證色彩準確度。DSPP 讀回仍全零，需繼續追實际硬體 block／bank 與提交。測試 XML 與原版庫均不作正式產品修改。


## 5. 目前實作（2026-10-06）

| 項目 | 位置 | 內容 |
|---|---|---|
| 校正檔 `hal_hdr` 模式 | `device/sony/poplardcm/extract-files.py` | `blob_fixup().regex_replace()`：限定原廠 55 模式／Default 101，複製 Default 為 `hal_hdr`（ModeID 200）並加入同檔 `hal_native` 的 feature 25（Virtual PCC，保留 `Disable=1`）；已有 `hal_hdr` 時不再修改 |
| 校正檔雜湊 | `device/sony/poplardcm/proprietary-files.txt` | `qdcm_calib_data_{6,9}.xml|<原廠 sha1>|<修補後 sha1>` |
| 提取結果 | `vendor/sony/poplardcm/proprietary/vendor/etc/qdcm_calib_data_{6,9}.xml` | `NumModes="56"`，各含 1 個 `hal_hdr`（雜湊與上一列第二個值相符） |
| 讓核心產生 3D LUT | `device/sony/yoshino-common/system.prop` | 移除 `sdm.disable_hdr_lut_gen=1` |
| 明確設定核心屬性 | `device/sony/poplardcm/vendor.prop` | `vendor.display.disable_hdr_lut_gen=0`（`libsdmcore` 讀這個名字） |
| HWC 寬色域 | `device/sony/yoshino-common/BoardConfigCommon.mk` | `TARGET_HAS_WIDE_COLOR_DISPLAY := true`。`hardware/qcom-caf/common/BoardConfigQcom.mk` 會據此設 `SOONG_CONFIG_qtidisplay_wide_color`，使 `hwc2` 編入 `FEATURE_WIDE_COLOR`（**是編譯旗標，不是系統屬性**，`getprop` 查不到屬正常） |
| 核心 HDR 宣告 | `kernel/sony/msm8998`（`mdss_mdp.c`、`dsi-panel-poplar.dtsi`） | 保留硬體 HDR quirk 與三個面板的 `qcom,mdss-dsi-panel-hdr-enabled`（已在遠端，無待提交） |
| HWC 2.3 與亮度 | `hardware/qcom-caf/msm8998/display`（提交 `8d20cec78`） | 與 HDR 無關；已列入 `.repo/local_manifests/lineage-22.2_FeliCa.xml`，來源為 `h0353914/android_hardware_qcom_display` |

**沒有做的事：** 沒有改 `libsdmcore`／`libsdm-color`／`libsdmextension`／`libhdr_tm`（皆為預編譯）、沒有在 HWC 填 LUT、沒有移植原廠 `PrepareSomc`／`br2tm.xml`／`tminv_dat*`。原廠式的 `SMH0_*` 亮度模式切換（原第 5.2 節）仍是可選的後續工作，目前不需要。

**已知無害的警告：** 播放 HDR 時 composer 服務會記一筆 `HwcComposer: command 0x3030000 generated error 8`。`0x3030000` 是 `SET_LAYER_PER_FRAME_METADATA`（`composer/2.2/IComposerClient.hal`），`8` 是 `UNSUPPORTED`：msm8998 的 CAF HWC 沒有實作這個函式（sdm845 才有），HDR 資訊改由 gralloc buffer metadata（`qdMetaData` 的 `GET_COLOR_METADATA`）取得，SurfaceFlinger 對 `UNSUPPORTED` 也不當錯誤處理。每次開始播放只出現一兩筆，**不建議補實作**（需動 `HWCLayer` 欄位，而 `libsdmcore` 是預編譯檔，風險大於好處）。

---

## 6. 驗證結果

### 6.1 測試影片（同一畫面、四種格式）

位置：`SemcCameraUI/.tmp/hdrvid/`；產生腳本 `gen_hdr.py`（需 `.tmp/fridaenv` 內的 numpy 與 `.tmp/ffpath.txt` 指向的 ffmpeg）。已推到兩台的 `/sdcard/Movies/`，兩台與電腦上的 SHA-256 一致。

| 檔案 | 格式 | SHA-256（前 16 碼） |
|---|---|---|
| `vivid_hevc_hdr10.mp4` | HEVC Main10，PQ | `688808c38015f0c8` |
| `vivid_hevc_hlg.mp4` | HEVC Main10，HLG | `87c5150fc4e79bee` |
| `vivid_vp9p2_hdr10.webm` | VP9 Profile 2，PQ | `51983f70bad0ee7c` |
| `vivid_av1_hdr10.mp4` | AV1 10-bit，PQ | `a861994b5d5e8e3d` |

畫面（1080p、8 秒）：上半滿飽和色相條（亮度 20→1000 nits、色相流動）；中間 100／203／400／700／1000 nits 白色塊；下半 RGB／CMY 各三級亮度；另有 1000 nits 移動亮點。色域 BT.2020，PQ 版帶 mastering metadata（MaxCLL 1000）。**只有色相條與亮點會動，其餘色塊是固定的校準色塊。**

### 6.2 實測（播 `vivid_hevc_hdr10.mp4`，Glimpse）

| 項目 | r11 | BH904ULGAT（刷新版後） | BH904ULGAT（舊版） |
|---|---|---|---|
| ROM | `22.2-20261003` | `22.2-20261003` | `22.2-20260927` |
| `qdcm_calib_data` 模式數／`hal_hdr` | 56／有 | 56／有 | 55／無 |
| `Invalid Lut Entries` | 0 | **0** | **2078** |
| `Error handling HDR in ToneMapper` | 0 | **0** | **2078** |
| 圖層 dataspace | `BT2020_ITU_PQ` | `BT2020_ITU_PQ` | `BT2020_ITU_PQ` |
| 解碼器 | 硬體 `OMX.qcom.video.decoder.hevc` | 同左 | 同左 |
| `HandleHDR: Setting color mode = hal_hdr` | 有 | 有 | 未檢查 |
| 使用者目視 | 正常 | 正常 | 卡幀（使用者判斷） |

### 6.3 尚未驗證

- 面板實際亮度（nits）、各亮度色塊的層次、色彩準確度。這些沒有儀器量測，DSPP 暫存器也不在 debugfs 可讀範圍（`MSMFB_MDP_PP` 讀回全零，未交叉驗證，見 4.6）。
- 「`vendor.display.disable_hdr_lut_gen` 屬性不存在」與「設為 0」是否行為相同：`setprop` 無法清成空值，無法驗證；已改為在 `vendor.prop` 明確設 `0` 並驗證（6.4）。
- HLG、VP9.2、AV1 三支測試影片在這台手機上能否解碼播放，還沒逐一驗證。
- 畫面更新頻率：`dumpsys SurfaceFlinger --latency` 在這個版本對影片圖層回傳空表，量不到幀間隔；卡幀消失只有間接證據（每幀錯誤歸零）加使用者目視。

### 6.4 加入 `vendor.display.disable_hdr_lut_gen=0` 後的 r11 驗證（2026-10-06）

在 `device/sony/poplardcm/vendor.prop` 明確加入該屬性（提交 `ade3a0a`）並重新編譯（`make bacon -j10`，耗時 9 分 34 秒），產物 `vendor/build.prop` 第 187 行含 `vendor.display.disable_hdr_lut_gen=0`。用新規範 `adb push` ＋ `adb shell twrp install /sdcard/rom.zip` 刷入 r11（輸出 `script succeeded: result was [1.000000]`，recovery 內 `/sdcard` 可寫），重開機後：

| 項目 | 結果 |
|---|---|
| `ro.lineage.version` | `22.2-20261005-UNOFFICIAL-poplardcm` |
| `getprop vendor.display.disable_hdr_lut_gen` | `0`；`sdm.disable_hdr_lut_gen` 為空 |
| `qdcm_calib_data_9.xml` 的 `hal_hdr` | 1 個 |
| 播 `vivid_hevc_hdr10.mp4`（12 秒） | `Invalid Lut Entries` 0、`Error handling HDR in ToneMapper` 0、`E SDM` 0、`HandleHDR: Setting color mode = hal_hdr` 1 筆 |
| 解碼器／圖層 | 硬體 `OMX.qcom.video.decoder.hevc`；dataspace `BT2020_ITU_PQ` |

結論：明確設為 `0` 的版本行為與先前測過的 ROM 一致。「屬性不存在」是否等價仍沒有驗證，但已不需要，因為屬性現在固定寫在 `vendor.prop`。面板實際亮度與色彩仍只有目視，沒有儀器量測。

---

## 7. YouTube HDR（與顯示 HDR 路徑無關）

- 面板宣告 HDR10 後，YouTube 會選 `334`（720p VP9 Profile 2 HDR）等 HDR 串流。**沒有任何硬體或系統解碼器宣稱支援 VP9 Profile 2**：`OMX.qcom.video.decoder.vp9` 的 profile 列表是空的（CAF `omx_vdec_v4l2.cpp` 對 VP9 回 `OMX_ErrorNoMore`），AOSP 軟體解碼器 `c2.android.vp9.decoder` 雖宣告 2HDR，但 YouTube 並不使用它。
- `334` 實際走 **YouTube 內建 libvpx 軟體解碼**，再由 YouTube 自己的 GL（log：`GlWindowFactory: DCIP3 GAMMA22`）轉成 DCI-P3 SDR 輸出；SurfaceFlinger 圖層 dataspace 只有 `V0_SRGB`。所以 YouTube 不會觸發 HWC 的 HDR 色調映射或 `hal_hdr`，有沒有 `hal_hdr` 看不出差異。
- 原廠機 SOV36（Android 9、YouTube 21.23.483）對照：同樣播 `333`／`334`，log 為 `Codec reused by ExoPlayer: libvpxv1.16.0-134-gab83db610`，路徑相同。
- 偶發綠屏／卡住：YouTube 選 `334` 後沒向 MediaCodec 要影片解碼器，CPU 閒置，重試 4 次後退回 itag 18（H.264）才播放。已排除：顯示器的 HDR 宣告（對 App 隱藏 HDR 後仍會發生）、AOSP 軟體 VP9 解碼器（從 `media_codecs.xml` 拿掉後仍會發生）。原因仍未查明，推測是 YouTube 內建軟體解碼路徑在首次使用時沒有啟動。
- 要驗證顯示 HDR 路徑，請用本機的 HEVC HDR10 影片（6.1），不要用 YouTube。
- 重現工具：`.tmp/ytrepro.py`（`--clear` 先清資料、`--hook` 以 Frida 啟動）、`.tmp/ythook.py`、`.tmp/fridaenv/`。

---

## 8. 提交紀錄（2026-10-06，均未 push）

| 專案 | 提交 | 內容 |
|---|---|---|
| `device/sony/yoshino-common`（`lineage-22.2`） | `24d8bf8d` yoshino-common: display: Enable wide color and let the core generate HDR 3D LUTs | `BoardConfigCommon.mk` 加 `TARGET_HAS_WIDE_COLOR_DISPLAY := true`；`system.prop` 移除 `sdm.disable_hdr_lut_gen=1` |
| `device/sony/poplardcm`（`lineage-22.2_FeliCa`） | `ade3a0a` poplardcm: display: Add a hal_hdr QDCM mode for hardware HDR | `extract-files.py`（hal_hdr fixup）、`proprietary-files.txt`（雜湊）、`vendor.prop`（`vendor.display.disable_hdr_lut_gen=0`） |
| `vendor/sony/poplardcm`（`lineage-22.2_felica`） | `c01e86f` poplardcm: Add the hal_hdr mode to the QDCM calibration files | `qdcm_calib_data_{6,9}.xml` 各 13 行變動 |
| `SemcCameraUI`（`main`） | 見 `git log` | `AGENTS_build.md`（第 6 節 `twrp install`）、本文件 |

kernel、`hardware/qcom-caf/msm8998/display`、`hardware/lineage/livedisplay`、`packages/apps/Nfc` 皆乾淨且與遠端同步。這三個 LineageOS 相關提交都在遠端之前 1 個提交，**尚未 push**。

---

## 9. 手機目前狀態

| 手機 | ROM | 備註 |
|---|---|---|
| r11（QV700WMR11） | `22.2-20261005`（含 `vendor.prop` 明確設 `0`，見 6.4） | 以 `twrp install` 刷入並驗證 |
| BH904ULGAT | `22.2-20261003`（以 `twrp sideload` 刷入，原本是 `20260927` 舊版） | 尚未刷 `20261005`；與 r11 的差別只在 `vendor.prop` 是否明確設 `0` |

兩台都有測試影片（6.1）與臨時測試用的 `.tmp/` 工具（Frida server 已移除、port forward 已清除、`stay_on_while_plugged_in` 原為 0）。

---

## 10. 量測工具與重現方式

### 10.1 HWC 畫面傾印

`display.qservice` 註冊在 **vndbinder**，`service call` 打不到。用臨時小工具 `qsdump`（呼叫 `qService::IQService::SET_FRAME_DUMP_CONFIG`，指令碼 21）：

```
qsdump <張數> <遮罩>      # 遮罩 1 = 輸入圖層，2 = 輸出
qsdump 0 0                 # 停止傾印
```

- **必須放 `/vendor/bin` 執行**，放 `/data/local/tmp` 會連到系統版 libbinder 而失敗（`Mixing copies of libbinder`）。
- 輸出在 `/data/vendor/display/frame_dump_primary/`：`input_layerN_*.raw`、`tonemap_WxH_frameK.raw`。
- **不要用遮罩 2**：會讓每個畫面提交失敗（`HWPrimary::Commit: Invalid output buffer fd`）。
- 畫面緩衝區預設是 UBWC 壓縮，傾印前要暫時加 `vendor.gralloc.disable_ubwc=1`（只關 `enable_fb_ubwc` 無效），量完要拿掉。

### 10.2 其他

| 目的 | 指令／位置 |
|---|---|
| 看圖層合成與色彩欄位 | `dumpsys SurfaceFlinger`，看 `------------SDM` 區段；色彩欄位 6=BT601、1=BT709、9=BT2020。**表中格式欄位不會反映色調映射後的格式** |
| 看 SurfaceFlinger 的 HDR 判斷 | `dumpsys SurfaceFlinger \| grep "HWC Support"` |
| 看 QDCM 模式 | `service call vendor.lineage.livedisplay.IDisplayModes/default 1`（列出）、`2`（目前）、`4 i32 <id> i32 0`（切換） |
| 看核心色彩模式切換 | `logcat \| grep "Setting color mode"` |
| 核心 PP 除錯 | `echo "file mdss_mdp_pp.c +p" > /sys/kernel/debug/dynamic_debug/control`（只記錄套用了哪些功能，不含數值） |
| GPU 負載 | `cat /sys/class/kgsl/kgsl-3d0/gpubusy` |
| 硬體解碼測試 | 自寫 `MediaCodec` 小工具＋ libvpx 測試向量（`vp92-2-20-10bit-yuv420.webm`），`dmesg` 看 `msm_vidc`（先 `echo 0x1f > /sys/kernel/debug/msm_vidc/debug_level`，用完改回 `0x3`） |
| 原廠韌體解包 | `.sin` 是 gzip 的 tar，內含稀疏分塊，用 `simg2img` 合併後以 `debugfs_static` 取檔 |
| 影片播放測試 | 先 `am broadcast ... MEDIA_SCANNER_SCAN_FILE`，再用 `content://media/external/video/media/<id>` 開啟 |

DSPP 的色彩校正暫存器不在核心 debugfs 可讀範圍內，所以「面板最終輸出」沒有辦法直接量。


---

## 11. 待決定

1. 是否 push 第 8 節的三個提交。
2. 6.4 驗證通過後，確認 `vendor.display.disable_hdr_lut_gen=0` 要不要保留在 `vendor.prop`（建議保留，行為與已測 ROM 一致）。
3. 是否追查 YouTube 偶發綠屏（例如在 r11 裝原廠機上的舊版 YouTube 21.23.483 對照，區分是 App 版本或 Android 版本造成）。
4. 是否做原廠式 `SMH0_*` 亮度模式切換（需改 HWC，目前不需要）。
5. 面板實際亮度與色彩準確度的量測方式。

---

## 12. 調查歷史補充（2026-10-03～04）

- **10-03 留置測試狀態：** 曾以臨時核心 #60（能力列含 `hdr`）、`vendor.display.disable_hdr_lut_gen=0`、補齊 PCC 的 XML 做手動測試，forward checksum 為 27244724；那些是手機上的暫時修改，已由後來刷入完整 ROM 取代。
- **10-03 設備樹帶入：** 把上述測試配置帶入設備樹與 vendor 庫（`qdcm_calib_data_{6,9}.xml` 加 `hal_hdr`＋feature 25、`vendor.prop` 加 `vendor.display.disable_hdr_lut_gen=0`、移除 common `vendor.prop` 先前新增的關閉屬性、kernel `dsi-panel-poplar.dtsi` 恢復三個面板 HDR enabled 旗標）。
- **10-04 提取修補：** 依要求移除自訂 def，改用既有 `blob_fixup().regex_replace()`（見第 5 節）。三款原廠韌體（G8341、G8142、G8441）的完整 QDCM XML 各不相同，但六份 Virtual PCC payload 相同，因此不能把完整 XML 共用；參考檔與比對在 `/home/h/tmp/o/README.md` 與 `calibration_comparison.json`。
- **原第 5 節舊做法（已被取代）：** 曾建議核心拿掉 `MDSS_QUIRK_HDR_SUPPORT_ENABLED`、由 SurfaceFlinger 以 GPU 做 HDR→SDR，並建議還原 `TARGET_HAS_WIDE_COLOR_DISPLAY`、`sdm.disable_hdr_lut_gen` 等改動；後來改走硬體 HDR 路徑，這些改動反而保留，kernel 的 HDR quirk 也保留。核心提交 `63be40695758`（拿掉面板 HDR 旗標）只存在於本機分支 `hdr_sdr`，不在 `lineage-22.2_ksu`，不會進入目前的 ROM。
