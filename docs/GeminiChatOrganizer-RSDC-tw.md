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
- **缺乏本地備份**：雲端對話搜尋不便，且無法在離線狀態下進行二次編輯與整理。  
- **元數據缺失**：導出的文本往往缺乏精確的提問時間，難以還原思考脈絡。

### 1.4 系統目標 (System Goals)

- **全量下載**：支援將雲端對話完整鏡像至本地路徑。  
- **精確過濾**：提供界面讓使用者篩選（隱藏/顯示）特定對話區塊。  
- **脈絡保留**：強制紀錄每一輪對話的日期與時間戳。  
- **標準化產出**：最終結果必須能轉化為符合業界標準的 Markdown 格式。

## 2. Specification (規格) — 「系統的規則是什麼？」

### 2.1 核心架構層級 (Hierarchy)

- **Archive (封存區)**：系統最高的數據容器，儲存所有下載的對話。  
- **Session (對話單元)**：單一主題的對話鏈。  
- **Turn (輪次)**：最小的邏輯單位，包含一個 Prompt（提問）與一個 Response（回答）。

### 2.2 Artifact 類型與流向

- **Raw Source (原始源)**：從 Gemini API/下載獲取的原始數據（包含所有歷史紀錄）。  
- **Selection State (篩選狀態)**：針對每個 Turn 的顯示/隱藏標記，此標記必須可持久化。  
- **Final Artifact (最終產物)**：根據篩選狀態生成的 Markdown 文件。

### 2.3 命名與數據結構

- **時間戳規範**：統一使用 YYYY-MM-DD HH:mm:ss 格式。  
- **狀態屬性**：每個對話輪次必須具備 `visibility_flag` (布林值) 與 timestamp 屬性。

### 2.4 配置規範 (Config Schemas)

- `sync_config.yaml`：定義下載頻率、儲存路徑。  
- `export_template.yaml`：定義 Markdown 輸出模板（如：是否在標題顯示時間戳、換行格式）。

### 2.5 UI 互動 (UI Interaction)

- **可見性切換 (Visibility Toggle)**：每個輪次 (Turn) 必須在標頭起始端提供一個切換控制項，可即時翻轉其 `visibility_flag`。狀態變更必須立即持久化（不需另行儲存）。  
- **隱藏已隱藏項目過濾器 (Hide-Hidden Filter)**：UI 必須提供一個全域切換；啟用時，將 `visibility_flag` 為 `false` 的輪次從輪次檢視中移除。當此過濾器啟用時，所有輪次皆已隱藏的對話單元 (Session) 也必須從清單中移除，並在其中任一輪次再次變為可見時自動重新出現。  
- **對話單元排序順序 (Session Sort Order)**：對話單元清單必須能依起始時間進行升冪或降冪排序；排序方向為僅檢視層的偏好設定，不得影響持久化狀態。

## 3. Design (設計) — 「系統如何架構？」

### 3.1 核心組件職責

- **Node.js Bridge (橋接器)**：  
  - 負責運作 UI 介面。  
  - 管理 Python 核心進程的生命週期。  
  - 處理使用者在介面上的點擊行為（隱藏/顯示操作）。  
- **Python Processing Core (處理核心)**：  
  - **Downloader**：與 Gemini 接口對接，執行數據抓取。  
  - **Parser**：將原始數據解析為規範定義的 Turn 物件。  
  - **Exporter**：根據篩選狀態與模板，合成 Markdown 檔案。  
- **Local Repository (本地倉庫)**：存放原始與處理後的數據檔案。

### 3.2 目錄結構

```
ui/                  Node.js 前端代碼
engine/              Python 核心邏輯代碼
warehouse/
├── raw/             下載的原始 JSON
└── processed/       帶有狀態標記的數據
exports/             最終產出的 Markdown 檔案
```

### 3.3 執行流程

1. 使用者觸發「同步」，Node.js 呼叫 Python Downloader 下載數據至 warehouse/raw/。  
2. Python Parser 處理數據並回傳給 Node.js UI 顯示。  
3. 使用者在 UI 上切換 `visibility_flag`，狀態即時寫入 warehouse/processed/。  
4. 使用者執行「整理」， Python Exporter 讀取狀態並生成 .md。

## 4. Coding (實作規範) — 「程式碼怎麼寫？」

### 4.1 關鍵開發準則

- **IPC 驅動**：Node.js 與 Python 之間透過標準輸入輸出 (STDIN/STDOUT) 或本地 Socket 傳遞 JSON 數據，嚴禁直接操作對方的內存。  
- **動態路徑注入**：所有檔案路徑必須由 Node.js 在啟動 Python 時作為參數傳入，嚴禁在 Python 代碼中硬編碼 (Hardcode) 相對路徑。  
- **強類型宣告**：Python 端必須使用 typing 模組標註函數簽名。

### 4.2 實作工具與庫

- **Node.js**：使用 `child_process` 模組執行 Python。  
- **Python**：使用 pathlib 處理路徑，使用 pydantic 進行數據校驗，使用 markdown-it 或 jinja2 輔助生成文檔。

### 4.3 安全與健壯性

- **數據鎖定**：當 Python Exporter 正在讀取數據時，Node.js 介面應鎖定編輯功能，防止數據競爭。  
- **錯誤處理**：任何 Python 端的例外 (Exception) 必須封裝成 JSON 錯誤格式回傳給 Node.js UI。

### 4.4 任務生成

- 使用自動化腳本確保開發環境中的 Python 依賴項 (requirements.txt) 與 Node 依賴項同步。
