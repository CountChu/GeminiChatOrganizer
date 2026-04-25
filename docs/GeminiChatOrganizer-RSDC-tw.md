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

### 1.5 主題聚合需求 (Topic Aggregation)

- **碎片化問題**：自動切分的 Session 可能因暫時中斷而導致同一主題散落在多個 Session。  
- **管理維度**：使用者需要從「時間線管理」提升到「專案/知識點管理」。

## 2. Specification (規格) — 「系統的規則是什麼？」

### 2.1 核心架構層級 (Hierarchy)

#### 2.1.0 Topic (主題層)

- **定義**：由使用者手動創建的邏輯容器，用於聚合一個或多個 Session。  
- **屬性**：`topic_id`, `name`, `description`, `session_ids` (有序列表), `tags`, `created_at`。

#### 2.1.1 Archive (封存區)

- **定義**：系統最高的數據容器，儲存所有 Topic 與未分類的 Session。

#### 2.1.2 Session (對話單元)

- **定義**：一組在語意上或時間上連續的對話主題鏈。  
- **屬性**：`session_id`, `title`, `turns` 列表, `start_time`, `last_active_time`。

#### 2.1.3 Turn (輪次)

- **定義**：系統中最小的邏輯互動單位。  
- **屬性**：`turn_id`, `prompt`, `response`, `timestamp`, `visibility_flag`。

### 2.2 Artifact 類型與流向

- **Raw Source (原始源)**：Google Takeout 原始 JSON。  
- **Processed JSON**：經 Parser 處理後的結構化數據。  
- **Topic Metadata**：儲存於 `warehouse/topics/` 下的 JSON，定義 Session 映射關係。  
- **UI MD Cache**：由 UI 渲染組件生成的單一輪次 Markdown 檔案。  
- **Final Artifact**：使用者最後導出的合併 Markdown 檔案（以 Topic 或單一 Session 為單位）。

### 2.3 命名與數據結構

- **時間戳規範**：統一使用 YYYY-MM-DD HH:mm:ss 格式。  
- **狀態屬性**：每個輪次必須具備 `visibility_flag` 與 `timestamp` 屬性。

### 2.4 配置規範 (Config Schemas)

- `sync_config.yaml`：定義 `session_gap_seconds` (預設 1800s)。  
- `export_template.yaml`：定義 Markdown 輸出樣式。

### 2.5 Session 推論規則

- **時間差啟發式**：相鄰 Turn 間隔 > 30 分鐘則切分為不同 Session。

### 2.6 自動標題生成

- **首句擷取**：擷取該 Session 第一個 Turn 提問內容的前 20 個字元。

### 2.7 Topic 管理規則

- **手動歸位**：使用者可在 UI 勾選多個 Session 並點擊「Create Topic」或「Add to Topic」。  
- **排序靈活性**：在 Topic 內部，使用者可以手動調整 Session 的先後順序。  
- **解散與移動**：刪除 Topic 不會刪除 Session，僅解除關聯，將 Session 放回「未分類 (Uncategorized)」區域。

### 2.8 UI 互動規則

- **可見性切換**：即時更新 `visibility_flag` 並反映在 UI 預覽。  
- **多選模式 (Batch Select)**：支援批量選取 Session 進行 Topic 歸類。  
- **主題導覽**：左側側邊欄顯示「主題」與「未分類 Session」。  
- **整理動作 (Organize Action)**：  
  - 產出文件前須先請求確認。  
  - 執行期間 UI 鎖定。  
  - 完成時報告產出文件數量。

## 3. Design (設計) — 「系統如何架構？」

### 3.1 核心組件職責

- **Node.js Bridge**：入口管理、UI Server 提供、生命週期監控。  
- **Python Processing Core**：  
  - **Parser**：數據解析。  
  - **Topic Manager**：處理 Topic 與 Session 的關聯讀寫。  
  - **Renderer**：生成 UI 用的單輪 MD 快取。  
  - **Exporter**：合併 MD 快取生成最終報告。  
- **Local Repository**：`visibility_flag` 與狀態儲存於 `warehouse/processed/session_<id>.json`。

### 3.2 目錄結構

```
ui/                  Node.js 前端代碼 (React/Vue/HTML)
engine/              Python 核心邏輯
├── parser.py        解析 Takeout 數據
├── topic_mgr.py     管理主題邏輯
├── render_md.py     生成 UI 用 MD 快取
└── exporter.py      生成最終合併檔案
warehouse/
├── raw/             原始 JSON (Google Takeout)
├── processed/       結構化 JSON (Session 數據與可見性旗標)
├── topics/          主題定義 JSON (定義 Session 映射與順序)
└── turns_md/        由 Renderer 生成的單一輪次 MD 檔案庫
exports/             最終產出的 Markdown 檔案
```

### 3.3 執行流程

1. **啟動 (Startup)**：執行 `render_md.py` 確保快取同步。  
2. **預渲染 (Pre-rendering)**：檢查 `processed/` 與 `turns_md/` 的同步狀態。  
3. **載入 UI**：前端讀取 Metadata 與 MD 快取內容。  
4. **狀態變更**：使用者操作 `visibility_flag` 或 Topic 歸類，立即寫回 JSON。  
5. **最終導出**：Exporter 依序讀取各 Session/Turn 內容並物理合併。

### 3.4 資料目錄角色

| 目錄 | 所有者 | 可變性 | 觸發時機 |
| :---- | :---- | :---- | :---- |
| `data/raw/` | 使用者輸入 | 唯讀 | 初始導入 |
| `warehouse/processed/` | Parser / Bridge | 狀態可變 | 初次解析 + 可見性切換 |
| `warehouse/topics/` | Topic Manager | 高可變 | 使用者定義主題時 |
| `warehouse/turns_md/` | Renderer | 內容不可變 | 內容變動或首次生成 |

## 4. Coding (實作規範)

### 4.1 關鍵開發準則

- **MD 為顯示基準**：UI 必須讀取生成的 `.md` 檔案，確保顯示與導出一致。  
- **增量更新**：`render_md.py` 檢查檔案雜湊或日期，避免重複渲染。  
- **無損處理**：不得修改 `data/raw/` 下的原始數據。

### 4.2 實作工具

- **Node.js**：`child_process.spawn` 調用 Python 核心。  
- **Python**：pathlib 處理路徑，jinja2 作為 MD 渲染引擎。

### 4.3 安全與健壯性

- **檔案命名**：使用 ID 命名，避免特殊字元。  
- **阻塞控制**：大批量渲染時應提供異步回饋或進度條。

### 4.4 Topic 實作細節

- **ID 生成**：建議 `topic_YYYYMMDD_random`。  
- **層級標題**：Topic 匯出時，Session 標題應作為二級標題（`## Session: [Title]`）。
