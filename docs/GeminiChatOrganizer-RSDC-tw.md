# Gemini 對話整理工具 (Gemini Chat Organizer) RSDC 說明文件

本文件定義了「Gemini 對話整理工具」的開發框架，旨在將原始的 AI 對話轉化為具備結構化價值的知識文檔。

## 1. Requirements (需求) — 「解決什麼問題？」

### 1.1 使用者對象 (Target Users)

- 頻繁與 Gemini 互動，並需要將對話內容產出為報告、筆記或開發紀錄的專業使用者。  
- 希望能在本地端保存與管理所有 AI 歷史紀錄的使用者。

### 1.2 核心願景 (Core Vision)

- 消除對話中的雜訊，讓 AI 對話從「過程工具」升格為「知識資產」，並提供全流程的數位溯源。

### 1.3 現狀痛點 (Current Pain Points)

- **過程雜訊過多**：對話中常包含多次修錯、重複嘗試的「過程性提問」，直接導出會導致重點模糊。  
- **缺乏本地備份**：雲端對話搜尋不便，且若在網頁版刪除後則無法找回。  
- **元數據缺失**：導出的文本往往缺乏精確的提問時間，難以還原思考脈絡。

### 1.4 系統目標 (System Goals)

- **全量下載與備份**：支援將雲端對話完整鏡像至本地路徑，且支援「本地優先」存儲。  
- **精確過濾**：提供界面讓使用者篩選（隱藏/顯示）特定對話區塊。  
- **脈絡保留**：強制紀錄每一輪對話的日期與時間戳。  
- **標準化產出**：最終結果必須能轉化為符合業界標準的 Markdown 格式。

## 2. Specification (規格) — 「系統的規則是什麼？」

### 2.1 核心架構層級 (Hierarchy)

#### 2.1.1 Archive (封存區)

- **定義**：系統最高的數據容器，儲存所有下載的歷史。

#### 2.1.2 Session (對話單元)

- **定義**：一組在語意上或時間上連續的對話主題鏈。  
- **屬性**：`session_id`, `title`, `turns` 列表, `start_time`, `last_active_time`。

#### 2.1.3 Turn (輪次)

- **定義**：系統中最小的邏輯互動單位。  
- **屬性**：`turn_id`, `prompt`, `response`, `timestamp`, `visibility_flag`。

### 2.2 Artifact 類型與流向

- **Raw Source (原始源)**：Google Takeout 原始 JSON。  
- **Processed JSON**：經 Parser 處理後的結構化數據。  
- **UI MD Cache**：由 UI 渲染組件生成的單一輪次 Markdown 檔案，供 UI 讀取顯示。  
- **Final Artifact**：使用者最後導出的合併 Markdown 檔案。

### 2.3 命名與數據結構

- **時間戳規範**：統一使用 YYYY-MM-DD HH:mm:ss 格式。  
- **狀態屬性**：每個對話輪次必須具備 `visibility_flag` 與 `timestamp` 屬性。

### 2.4 配置規範 (Config Schemas)

- `sync_config.yaml`：定義 `session_gap_seconds` (預設 1800s)。  
- `export_template.yaml`：定義 Markdown 輸出樣式。

### 2.5 Session 推論規則

- **時間差啟發式**：相鄰 Turn 間隔 > 30 分鐘則切分為不同 Session。

### 2.6 自動標題生成

- **首句擷取**：擷取該 Session 第一個 Turn 提問內容的前 20 個字元。

### 2.7 UI 互動規則

- **可見性切換**：即時更新 `visibility_flag`。  
- **Markdown 渲染驅動**：UI 不直接解析 JSON 文本，而是讀取預先生成的 MD 檔案路徑進行渲染。

## 3. Design (設計) — 「系統如何架構？」

### 3.1 核心組件職責

- **Node.js Bridge (橋接器)**：  
  - **App 入口**：啟動時自動觸發 `render_md_files.py`。  
  - **UI Server**：讀取 `warehouse/turns_md/` 下的檔案並回傳給網頁前端。  
  - **生命週期管理**：監控 Python 進程狀態。  
- **Python Processing Core (處理核心)**：  
  - **Parser**：將原始數據轉為結構化 JSON 存於 `processed/`。  
  - **Renderer (`render_md_files.py`)**：**核心同步組件**。遍歷所有 Turn，將 Prompt 與 Response 渲染成獨立的 `.md` 檔案存放於快取目錄。  
  - **Exporter**：合併選定的 MD 快取，生成最終報告。  
- **Local Repository**：本地數據倉庫。

### 3.2 目錄結構

```
ui/                  Node.js 前端代碼 (React/Vue/HTML)
engine/              Python 核心邏輯
├── parser.py        解析 Takeout 數據
├── render_md.py     (render_md_files.py) 生成 UI 用 MD 檔
└── exporter.py      生成最終合併檔案
warehouse/
├── raw/             原始 JSON
├── processed/       結構化 JSON (含 metadata)
└── turns_md/        由 Renderer 生成的單一輪次 MD 檔案庫
exports/             最終產出的 Markdown 檔案
```

### 3.3 執行流程

1. **啟動階段 (Startup)**：App 啟動，Node.js 即刻執行 `python engine/render_md.py`。  
2. **預渲染 (Pre-rendering)**：`render_md.py` 檢查 `processed/` 數據，為每個 `turn_id` 在 `warehouse/turns_md/` 下產出對應的 `.md`。  
3. **介面載入 (UI Loading)**：Node.js 將 MD 檔案清單與 Metadata 傳給前端，前端直接讀取 MD 內容顯示。  
4. **互動切換**：使用者切換 `visibility_flag`，Node.js 更新 JSON 數據，前端根據狀態標記隱藏/顯示對應的 MD 區塊。  
5. **最終導出**：Exporter 讀取選定的 MD 區塊進行物理合併。

## 4. Coding (實作規範) — 「程式碼怎麼寫？」

### 4.1 關鍵開發準則

- **MD 為顯示基準**：UI 嚴禁自行實作 Markdown 轉 HTML 邏輯，必須讀取 Python 生成的 `.md` 檔案，以確保顯示與導出的一致性。  
- **增量更新 (Incremental Rendering)**：`render_md.py` 應具備檢查機制，若 `processed/` 數據未變動且 MD 已存在，則跳過該輪次以加速啟動。  
- **無損處理**：不得修改原始下載數據。

### 4.2 實作工具與庫

- **Node.js**：`child_process.spawnSync` (用於啟動時的渲染同步) 或 `spawn`。  
- **Python**：pathlib 處理 MD 檔案路徑，jinja2 作為 MD 渲染引擎（定義 Prompt/Response 的佈局）。

### 4.3 安全與健壯性

- **檔案命名安全**：`turns_md/` 下的檔案應以 `turn_id` 命名，避免特殊字元導致讀取失敗。  
- **啟動阻塞控制**：若對話量極大，啟動渲染應採用非同步分段載入，或顯示進度條防止 UI 凍結。
