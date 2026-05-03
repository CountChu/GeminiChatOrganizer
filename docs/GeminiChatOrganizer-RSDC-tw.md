# Gemini 對話整理工具 (Gemini Chat Organizer) RSDC 說明文件

本文件定義了「Gemini 對話整理工具」的開發框架，旨在將原始的 AI 對話轉化為具備結構化價值的知識文檔。

## 1. Requirements (需求) — 「解決什麼問題？」

### 1.1 使用者對象 (Target Users)

- 頻繁與 Gemini 互動，並需要將對話內容產出為報告、筆記或開發紀錄的專業使用者。
- 希望能在本地端保存與管理所有 AI 歷史紀錄的使用者。

### 1.2 核心願景 (Core Vision)

- 消除對話中的雜訊，讓 AI 對話從「過程工具」升格為「知識資產」，並提供全流程的數位溯源。

### 1.3 現狀痛點 (Current Pain Points)

- **過程雜訊過多**：對話中包含多次修錯、重複嘗試的內容，導致重點模糊。
- **缺乏本地備份**：雲端對話搜尋不便，且刪除後無法找回。
- **元數據缺失**：導出的文本缺乏精確的提問時間，難以還原思考脈絡。

### 1.4 系統目標 (System Goals)

- **全量下載與備份**：支援將雲端對話鏡像至本地路徑，落實「本地優先」存儲。
- **精確過濾**：提供界面篩選（隱藏/顯示）特定對話輪次。
- **脈絡保留**：強制紀錄每一輪對話的日期與時間戳。
- **標準化產出**：最終結果轉化為標準 Markdown 格式。

### 1.5 主題聚合需求 (Topic Aggregation)

- **碎片化問題**：解決自動切分的 Session 因中斷而散落的問題。
- **管理維度**：提升至「專案/知識點管理」維度。

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
- updated: 每次對 Topic 進行異動（如增刪 Session、重排序、修改名稱）時，系統必須自動更新此時間戳。

#### Data - archive (封存區)

**定義**：系統最高的數據容器，儲存所有 Topic 與未分類的 Session。

#### Data - session (對話單元)

**定義**：一組在語意上或時間上連續的對話主題鏈。

**Syntax**

```
session = {sessionId, title, title2, beginTime, endTime, turns}
turns = [turn]
```

**Fields**

- `sessionId`: 唯一識別碼。
- `title`: Session 標題，預設由首句擷取生成。
- `title2`: 使用者可編輯的顯示標題。設定後，UI 以 `title2` 取代 `title` 顯示。預設為空字串。
- `beginTime` / `endTime`: Session 的起訖時間。

#### Data - turn (輪次)

**定義**：系統中最小的邏輯互動單位。

**Syntax**

```
turn = {turnId, timestamp, timestampUtc, kind, prompt, response, attachments, visibilityFlag}
```

**Fields**

- `timestamp`：本地時間的顯示欄位。適用 `YYYY-MM-DD HH:mm:ss` 格式規範；顯示於 Markdown 導出文件中。
- `timestampUtc`：直接保留自 Takeout 的原始值。作為排序與識別的基準鍵；用於推導 `turnId`（`T{unix_seconds}` 格式）以及計算 Session 切分的時間間隔。

**命名與數據結構規範**

- **時間戳規範**：統一使用 YYYY-MM-DD HH:mm:ss 格式。
- **狀態屬性**：每個輪次必須具備 `visibilityFlag` (Boolean) 與 timestamp 屬性。

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

**欄位與 Artifact 定義說明：**

- **`rawDir` (Raw Source)**：原始數據目錄。指向 Google Takeout 的原始對話 JSON。系統以此作為唯讀源。
- **`sessionsDir` (Processed JSON)**：結構化數據目錄。存儲經 Parser 處理後的 Session JSON。這是系統的「狀態核心」，承載內容及 `visibilityFlag`。
- **`turnsMdDir` (UI MD Cache)**：Markdown 快取目錄。由 Renderer 產出的逐輪 Markdown 檔案，供 UI 顯示使用。
- **`topicsDir` (Topic Metadata)**：主題定義目錄。存儲使用者定義的主題 JSON，建立 Session 間的邏輯映射。
- **`exportsDir` (Final Artifact)**：導出目錄。最終生成的合併 Markdown 文件存放處。
- **`sessionGapSeconds`**：切分閾值。定義兩次互動間隔超過此秒數則判定為新 Session。

#### Config - export_template.yaml

定義 Exporter 產出最終文檔時的佈局、外觀與命名規則。

```yaml
timestamp_in_header: true
turn_separator: "\\n\\n---\\n\\n"
filename_pattern: "{date}_{sid}_{slug}.md"
topic_filename_pattern: "{date}_{topic_id}_{slug}.md"
slug_max_chars: 40
session_header: "# {{ title }}"
topic_session_header: "## Session: {{ title }}"
turn_header: "## {{ timestamp }} — {{ prompt_preview }}"
prompt_block: "**Prompt:**\\n\\n{{ prompt }}"
response_block: "**Response:**\\n\\n{{ response_md }}"
```

### 2.3 Data Flow & Logic Rules

描述系統內數據轉化管線及其內嵌邏輯：

1. **`rawDir` -> `sessionsDir` (數據解析與自動切分)**
   - 讀取原始 Takeout JSON，執行時間戳修復與標準化。
   - **Session 推論規則**：相鄰 Turn 間隔 > `sessionGapSeconds` (預設 1800s) 則切分為不同 Session。
   - **自動標題生成**：擷取 Session 首輪提問前 20 字元作為預設 title。
   - 產出包含內容與預設 `visibilityFlag`: true 的 Session JSON。
2. **`sessionsDir` -> `turnsMdDir` (快取預渲染)**
   - 讀取 Session 狀態，將每一輪對話（Turn）獨立渲染為 Markdown 快取檔案。
   - 此步驟確保 UI 預覽與最終導出內容使用相同的渲染引擎。
3. **`sessionsDir` -> `topicsDir` (主題管理與歸位)**
   - **Topic 管理規則**：
     - 使用者在 UI 勾選 Session 並歸類至自定義主題。
     - **排序靈活性**：在 Topic 內部，使用者可手動調整 Session 先後順序。
     - **解散與移動**：刪除 Topic 僅解除邏輯關聯，不刪除 Session。
   - 產出主題定義 JSON (Topic Metadata)，建立物理數據間的邏輯映射。
4. **`topicsDir` -> `exportsDir` (最終物理合併)**
   - 依據主題定義之順序抓取 `turnsMdDir` 內的 Markdown 快取檔案進行合併。
   - 僅合併 `visibilityFlag`: true 的輪次，產出最終符合模板規範的知識文檔。

### 2.4 UI 互動規則

- **輪次可見性切換 (Per-turn Visibility)**：
  - 使用者可針對單一輪次（Turn）切換可見性。
  - 系統須即時更新該輪次的 `visibilityFlag` 並立即反映在 UI 預覽中。
- **Session 自動隱藏邏輯**：
  - 若某個 Session 內所有輪次的 `visibilityFlag` 皆為 false，則該 Session 視為隱藏。
  - 隱藏的 Session 不會顯示在側邊欄清單或搜尋結果中。
- **多選模式 (Batch Select)**：支援批量選取 Session 進行 Topic 歸類。
- **整理動作 (Organize Action)**：使用者明確觸發導出動作。
  - UI 在產出文件前須先請求確認。
  - **全局鎖定**：執行期間 UI 進入鎖定狀態，**禁止所有寫入操作**（包括可見性切換與主題異動），以避免數據競態。

## 3. Design (設計) — 「系統如何架構？」

### 3.1 核心組件職責

- **Node.js Bridge**：負責入口管理、提供 UI Server、與 Python 核心進行 IPC 通訊、監控生命週期。**必須強制執行導出期間的寫入鎖定 (Global Write Lock)**。
- **Python Processing Core**：
  - **Parser (`parser.py`)**：負責解析原始 JSON、修復時間戳及執行 Session 切分。
  - **Topic Manager (`topic_mgr.py`)**：負責處理主題的 CRUD 操作，並確保每次異動都更新 updated 時間戳。
  - **Renderer (`render_md.py`)**：負責讀取 Session JSON 並生成單輪 Markdown 快取。
  - **Exporter (`exporter.py`)**：負責讀取導出請求，依據 Topic/Session 順序合併可見的 MD 快取，生成最終產物。

### 3.2 資料目錄結構

系統目錄形成一條清晰的知識轉化管線。下表定義了各目錄的實體位置、所有權以及生命週期。

#### 目錄層級圖

```
data/
├── 0-raw/           原始 JSON 資料夾 (對應 rawDir)
├── 1-sessions/      結構化 JSON (對應 sessionsDir)
├── 2-turns_md/      逐輪 MD 快取 (對應 turnsMdDir)
├── 3-topics/        主題定義 JSON (對應 topicsDir)
└── 4-exports/       最終產出的 Markdown (對應 exportsDir)
```

#### 目錄角色定義

| 目錄 | 主要所有者 | 可變性 | 觸發時機 |
| :---- | :---- | :---- | :---- |
| `data/0-raw/` | 使用者 | 唯讀 | 初始導入數據 |
| `data/1-sessions/` | Parser | 狀態可變 | 初次解析 + UI 狀態切換 |
| `data/2-turns_md/` | Renderer | 內容不可變 | 內容變動或啟動時同步快取 |
| `data/3-topics/` | Topic Manager | 高可變 | 使用者定義/調整主題時 |
| `data/4-exports/` | Exporter | 唯讀產物 | 使用者執行「整理動作」後產出 |

### 3.3 執行流程

本節定義系統從啟動到導出的關鍵步驟，以及各組件間的交互關係。

1. **啟動與初始化 (Startup)**
   - **Node.js Bridge** 啟動 App，讀取 `sync_config.yaml` 並確認 data/ 目錄完整性。
   - 若偵測到新數據，**Node.js Bridge** 調用 **Parser (`parser.py`)** 進行原始 JSON 到 `data/1-sessions/` 的解析轉化。
2. **快取同步與預渲染 (Pre-rendering)**
   - **Node.js Bridge** 調用 **Renderer (`render_md.py`)**。
   - **Renderer** 比對 `data/1-sessions/` 的修改日期與 `data/2-turns_md/` 的現存快取，執行增量渲染，確保 UI 內容是最新的。
3. **載入介面與數據 (UI Loading)**
   - **Node.js Bridge** 從 `data/1-sessions/` 讀取 Session 列表，並篩選掉「所有輪次皆不可見」的 Session。
   - **Node.js Bridge** 從 `data/3-topics/` 讀取主題層級。
   - 前端（UI）透過 API 取得清單，並依據 `sessionId` 直接讀取對應的 .md 快取進行即時顯示。
4. **狀態變更與管理 (Interaction & Management)**
   - **可見性變更**：使用者切換開關，**Node.js Bridge** 立即更新 `data/1-sessions/` 中的 `visibilityFlag`。若 Session 變為隱藏狀態，UI 應立即從清單中移除。
   - **主題歸類**：使用者執行多選歸位，**Node.js Bridge** 調用 **Topic Manager (`topic_mgr.py`)** 更新 `data/3-topics/` 下的主題 JSON。
5. **合併導出 (Final Export)**
   - 使用者點擊導出，**Node.js Bridge** 確認選取的範圍（Topic 或 Session）。
   - **Node.js Bridge** 調用 **Exporter (`exporter.py`)**，依據邏輯順序抓取 `data/2-turns_md/` 的實體文件進行物理合併，產出至 `data/4-exports/`。

## 4. Coding (實作規範)

### 4.1 關鍵開發準則

- **MD 為顯示基準**：UI 必須讀取生成的 .md 檔案。
- **增量更新**：渲染引擎須檢查雜湊或日期，避免重複作業。
- **無損處理**：絕對不得修改 `0-raw/` 目錄下的原始數據。

### 4.2 實作工具

- **Node.js**：使用 `child_process.spawn` 調用 Python。
- **Python**：使用 `pathlib` 與 `jinja2` 引擎。

### 4.3 安全與健壯性

- **防禦數據競態**：當導出任務在進行中時，Node.js Bridge 必須阻塞所有寫入請求。
- **檔案命名**：使用 Unique ID 命名，避免特殊字元衝突。
- **阻塞控制**：處理時應提供進度回饋。

### 4.4 Topic 實作細節

- **ID 生成**：建議 topic_YYYYMMDD_random格式。
- **層級標題**：Topic 匯出時，Session 標題降階為二級標題 (## Session: [Title])。
