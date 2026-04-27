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

### 2.1 Data Hierarchy

#### Data - topic

**定義**：由使用者手動創建的邏輯容器，用於聚合一個或多個 Session。

**Syntax**

```
topic = {topicId, name, description, sessionIds, tags, created, updated}
sessionIds = [sessionId]
```

**Fields**

- `sessionIds`: 有序列表，決定匯出時 Session 的先後順序。

**Example**

```json
{
  "topicId": "topic_20260426_9b10f5",
  "name": "B 投資決策的關鍵解答",
  "description": "",
  "sessionIds": [
    "S1759563327",
    "S1759689500",
    "S1759773999"
  ],
  "tags": [],
  "created": "2026-04-26 07:22:59",
  "updated": "2026-04-26 08:33:59"
}
```

#### Data - archive (封存區)

**定義**：系統最高的數據容器，儲存所有 Topic 與未分類的 Session。

#### Data - session (對話單元)

**定義**：一組在語意上或時間上連續的對話主題鏈。

**Syntax**

```
session = {sessionId, title, beginTime, endTime, turns}
turns = [turn]
```

**Fields**

- `sessionId`: 唯一識別碼。
- `title`: Session 標題，預設由首句擷取生成。

#### Data - turn (輪次)

**定義**：系統中最小的邏輯互動單位。

**Syntax**

```
turn = {turnId, timestamp, timestampUtc, kind, prompt, response, attachments, visibilityFlag}
```

**命名與數據結構規範**

- **時間戳規範**：統一使用 `YYYY-MM-DD HH:mm:ss` 格式。
- **狀態屬性**：每個輪次必須具備 `visibilityFlag` (Boolean) 與 `timestamp` 屬性。

### 2.2 Configurations (配置規範)

系統行為與數據流（Artifacts）由兩個核心 YAML 檔案控管：

#### Config - sync_config.yaml

定義系統路徑、數據映射與解析規則。

```yaml
rawDir: "data/0-raw/Gemini Apps 260424"
sessionsDir: "data/1-sessions"
turnsMdDir: "data/2-turns_md"
topicsDir: "data/3-topics"
exportsDir: "data/4-exports"
sessionGapSeconds: 1800
```

#### Config - export_template.yaml

定義 Exporter 產出最終文檔時的佈局、外觀與命名規則。

```yaml
timestamp_in_header: true
turn_separator: "\n\n---\n\n"
filename_pattern: "{date}_{sid}_{slug}.md"
topic_filename_pattern: "{date}_{topic_id}_{slug}.md"
slug_max_chars: 40
session_header: "# {{ title }}"
topic_session_header: "## Session: {{ title }}"
turn_header: "## {{ timestamp }} — {{ prompt_preview }}"
prompt_block: "**Prompt:**\n\n{{ prompt }}"
response_block: "**Response:**\n\n{{ response_md }}"
```

### 2.3 Data Flow & Logic Rules

描述系統內數據轉化管線及其內嵌邏輯：

1. **rawDir -> sessionsDir (數據解析與自動切分)**
   - 讀取原始 Takeout JSON，執行時間戳修復與標準化。
   - **Session 推論規則**：相鄰 Turn 間隔 > `sessionGapSeconds` (預設 1800s) 則切分為不同 Session。
   - **自動標題生成**：擷取該 Session 第一個 Turn 提問內容的前 20 個字元作為預設 `title`。
   - 產出包含內容與預設 `visibilityFlag: true` 的結構化 Session JSON。
2. **sessionsDir -> turnsMdDir (快取預渲染)**
   - 讀取 Session 狀態，將每一輪對話（Turn）獨立渲染為 Markdown 快取檔案。
   - 此步驟確保 UI 預覽與最終導出內容使用相同的渲染引擎。
3. **turnsMdDir -> topicsDir (主題管理與歸位)**
   - **Topic 管理規則**：
     - 使用者在 UI 勾選 Session 並歸類至自定義主題。
     - **排序靈活性**：在 Topic 內部，使用者可手動調整 Session 先後順序。
     - **解散與移動**：刪除 Topic 不會刪除原始 Session，僅解除邏輯關連。
   - 產出主題定義 JSON (Topic Metadata)，建立物理數據間的邏輯映射。
4. **topicsDir -> exportsDir (最終物理合併)**
   - 依據主題定義之順序抓取 Markdown 快取檔案進行合併。
   - 僅合併 `visibilityFlag: true` 的輪次，產出符合模板規範的知識文檔。

### 2.4 UI 互動規則

- **可見性切換**：即時更新 `visibilityFlag` 並反映在 UI 中。
- **多選模式 (Batch Select)**：支援批量選取 Session 進行 Topic 歸類。
- **整理動作 (Organize Action)**：使用者明確觸發導出動作。
  - UI 在產出文件前須先請求確認。
  - 執行期間 UI 進入鎖定狀態，避免數據衝突。

## 3. Design (設計) — 「系統如何架構？」

### 3.1 核心組件職責

- **Node.js Bridge**：負責入口管理、提供 UI Server、與 Python 核心進行 IPC 通訊、監控生命週期。
- **Python Processing Core**：
  - **Parser (`parser.py`)**：負責解析原始 JSON、修復時間戳與執行 Session 自動切分邏輯。
  - **Topic Manager (`topic_mgr.py`)**：負責處理主題的 CRUD 操作，維護 Session 與 Topic 間的映射關係。
  - **Renderer (`render_md.py`)**：負責讀取 Session JSON，並利用 Jinja2 引擎生成對應的單輪 Markdown 快取。
  - **Exporter (`exporter.py`)**：負責讀取導出請求，依據 Topic/Session 順序合併可見的 MD 快取，生成最終產物。

### 3.2 目錄結構

```
data/
├── 0-raw/           原始 JSON
├── 1-sessions/      結構化 JSON (Session 數據與 visibilityFlag)
├── 2-turns_md/      逐輪 MD 快取
├── 3-topics/        主題定義 JSON
└── 4-exports/       最終產出的 Markdown
```

### 3.3 執行流程

1. **啟動 (Startup)**：系統初始化並同步 MD 快取狀態。
2. **預渲染 (Pre-rendering)**：檢查 `1-sessions/` 與 `2-turns_md/` 的同步狀態。
3. **載入 UI**：前端讀取 Metadata 與 MD 快取內容。
4. **狀態變更**：使用者操作 `visibilityFlag` 或 Topic 歸類。
5. **最終導出**：執行 Exporter 進行內容合併與物理寫入。

### 3.4 資料目錄角色

| 目錄 | 所有者 | 可變性 | 觸發時機 |
| :---- | :---- | :---- | :---- |
| `data/0-raw/` | 使用者輸入 | 唯讀 | 初始導入 |
| `data/1-sessions/` | Parser / Bridge | 狀態可變 | 初次解析 + 可見性切換 |
| `data/3-topics/` | Topic Manager | 高可變 | 使用者定義主題時 |
| `data/2-turns_md/` | Renderer | 內容不可變 | 內容變動或首次生成 |

## 4. Coding (實作規範)

### 4.1 關鍵開發準則

- **MD 為顯示基準**：UI 必須讀取生成的 `.md` 檔案。
- **增量更新**：渲染引擎須檢查雜湊或日期，避免重複作業。
- **無損處理**：絕對不得修改 `0-raw/` 目錄下的原始數據。

### 4.2 實作工具

- **Node.js**：使用 `child_process.spawn` 調用 Python。
- **Python**：使用 `pathlib` 處理跨平台路徑，`jinja2` 作為核心渲染引擎。

### 4.3 安全與健壯性

- **檔案命名**：使用 Unique ID 命名檔案，避免特殊字元造成系統衝突。
- **阻塞控制**：大批量處理時應提供進度條與非同步回饋。

### 4.4 Topic 實作細節

- **ID 生成**：建議 `topic_YYYYMMDD_random`。
- **層級標題**：Topic 匯出時，Session 標題應自動降階為二級標題 (`## Session: [Title]`)。
