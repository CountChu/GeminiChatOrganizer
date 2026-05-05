# Gemini 對話整理工具 (Gemini Chat Organizer) RSDC 說明文件

本文件定義了「Gemini 對話整理工具」的開發框架，旨在將原始的 AI 對話轉化為具備結構化價值的知識文檔。

### 1. Requirements (需求) — 「解決什麼問題？」

#### 1.1 使用者對象 (Target Users)

- 頻繁與 Gemini 互動，並需要將對話內容產出為報告、筆記或開發紀錄的專業使用者。
- 希望能在本地端保存與管理所有 AI 歷史紀錄的使用者。

#### 1.2 核心願景 (Core Vision)

- 消除對話中的雜訊，讓 AI 對話從「過程工具」升格為「知識資產」，並提供全流程的數位溯源。

#### 1.3 現狀痛點 (Current Pain Points)

- **過程雜訊過多**：對話中包含多次修錯、重複嘗試的內容，導致重點模糊。
- **缺乏本地備份**：雲端對話搜尋不便，且刪除後無法找回。
- **元數據缺失**：導出的文本缺乏精確的提問時間，難以還原思考脈絡。

#### 1.4 系統目標 (System Goals)

- **全量下載與備份**：支援將雲端對話鏡像至本地路徑，落實「本地優先」存儲。
- **精確過濾**：提供界面篩選（隱藏/顯示）特定對話輪次。
- **脈絡保留**：強制紀錄每一輪對話的日期與時間戳。
- **標準化產出**：最終結果轉化為標準 Markdown 格式。

#### 1.5 主題聚合需求 (Topic Aggregation)

- **碎片化問題**：解決自動切分的 Session 因中斷而散落的問題。
- **管理維度**：提升至「專案/知識點管理」維度。

### 2. Specification (規格) — 「系統的規則是什麼？」

#### 2.1 Data Hierarchy

##### Data - topic

**定義**：由使用者手動創建的邏輯容器，用於聚合一個或多個 Session。

**Syntax**

```
topic = {topicId, name, description, sessionIds, tags, created, updated}
sessionIds = [sessionId]
```

**Fields**

- `sessionIds`: 有序列表，決定匯出時 Session 的先後順序。
- `updated`: 每次對 Topic 進行異動（如增刪 Session、重排序、修改名稱）時，系統必須自動更新此時間戳。

##### Data - archive (封存區)

**定義**：系統最高的數據容器，儲存所有 Topic 與未分類的 Session。

##### Data - session (對話單元)

**定義**：一組在語意上或時間上連續的對話主題鏈。

**Syntax**

```
session = {sessionId, beginTime, endTime, turns}
turns = [turn]
```

**Fields**

- `sessionId`: 唯一識別碼。
- `beginTime` / `endTime`: Session 的起訖時間。

Session **不儲存** title 欄位；標題**永遠**由 Turn 動態推導。規則：取第一個 `visibilityFlag` 為 `true` 的 Turn — 其 `prompt2`（若已設定），否則 `prompt`（首行，截斷至 20 字元）。若無任何可見 Turn，退回首個 Turn 的 `prompt2` / `prompt`，使該 Session 仍具可辨識的名稱。標題於每次讀取時計算，**永不寫入 `data/1-sessions/*.json`**。

##### Data - turn (輪次)

**定義**：系統中最小的邏輯互動單位。

**Syntax**

```
turn = {turnId, timestamp, timestampUtc, kind, prompt, prompt2, response, attachments, visibilityFlag, missing}
```

**Fields**

- `timestamp`: 本地時間顯示欄位。統一使用 YYYY-MM-DD HH:mm:ss 格式；呈現於 Markdown 匯出中。
- `timestampUtc`: Takeout 原始值。作為排序的正規鍵；用於推導 `turnId`（T{unix_seconds}）及計算切分間隔。
- `kind`: 區分對話類型（如 prompted）。
- `prompt`: 來自 Takeout 的原始文字，不可變更。
- `prompt2`: 使用者編輯的標註／次要 `prompt`。若非空，渲染時將在 Prompt 區塊後額外輸出 Prompt2 區塊（原始 `prompt` 保持不變）。亦參與 Session 標題推導規則（見上方 Session）。預設為空字串。
- `response`: 對話回覆內容。
- `attachments`: 附件檔案名稱清單（如圖片）。
- `visibilityFlag`: 控制該輪次是否參與顯示與導出。
- `missing`: 布林值。僅由 Parser 設定為 `true`：當某 Turn 存在於次新原始目錄、卻已從最新原始目錄消失，且 `syncStrategy` 為 `archive` 時。預設為 `false`。與 `visibilityFlag` 相互獨立——使用者既有的可見性與 `prompt2` 設定不會被覆寫。

**命名與資料結構規則**

- **時間戳格式**：統一使用 `YYYY-MM-DD HH:mm:ss` 格式。
- **狀態屬性**：每個 Turn 必須攜帶 `visibilityFlag`（布林值）與 `timestamp` 屬性。

#### 2.2 Configurations (配置規範)

系統行為與資料流（Artifacts）由以下兩個核心 YAML 檔案所管控：

##### Config - sync_config.yaml

定義系統路徑、數據映射與解析規則。

```yaml
rawDir: "data/0-raw"
sessionsDir: "data/1-sessions"
turnsMdDir: "data/2-turns_md"
topicsDir: "data/3-topics"
exportsDir: "data/4-exports"
sessionGapSeconds: 1800
syncStrategy: "archive" # archive: 原始資料刪除後本地保留; mirror: 同步刪除
```

**欄位定義：**

- **rawDir（原始來源）**：原始資料根目錄。包含一或多個以 `Gemini Apps YYMMDD` 命名的 Takeout 子目錄；Parser 掃描其中執行兩代差異比對。系統視為唯讀。降階相容：若 `rawDir` 本身即包含活動 JSON（無符合命名的子目錄），Parser 對該目錄執行單目錄全量解析。
- **sessionsDir（結構化 JSON）**：結構化資料目錄。儲存系統狀態 JSON。由 Parser 寫入結構，Bridge 寫入使用者狀態（Flag/Prompt2）。為系統的「狀態核心」。
- **turnsMdDir（UI MD 快取）**：Markdown 快取目錄。由 Renderer 產出的逐 Turn Markdown 檔案，供 UI 顯示。
- **topicsDir（主題後設資料）**：主題定義目錄。儲存使用者定義的 Topic JSON，建立 Session 間的邏輯映射。
- **exportsDir（最終產物）**：匯出目錄。最終合併的 Markdown 文件儲存處。
- **sessionGapSeconds**：切分閾值。若兩相鄰互動間隔超過此秒數，視為新 Session。
- **syncStrategy**：同步策略。archive（預設）：原始資料目錄若刪除聊天記錄，本地已解析數據予以保留；mirror：嚴格同步刪除。

##### Config - export_template.yaml

定義 Exporter 產出最終文件時的版面、外觀與命名規則。

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

#### 2.3 Data Flow & Logic Rules

1. **rawDir -> sessionsDir (兩代差異比對與增量更新)**
   - **命名慣例**：rawDir 下的子目錄以 Gemini Apps YYMMDD 格式命名。
   - **增量比對機制**：系統解析日期並選取**日期最近的兩個子目錄**進行內容比對。
   - **差異識別**：以「最新目錄」為基準與「次新目錄」比對。識別出新增的 Turn、編輯內容或刪除紀錄。
   - **降階處理**：若僅存在單一原始目錄，則對該目錄執行全量解析導入。
   - **狀態合併**：新發現的數據併入 sessionsDir。必須確保 `timestampUtc` 為唯一鍵，且**不得覆蓋**本地已存在的 `prompt2` 或 `visibilityFlag`。
   - **刪除處理**：依據 syncStrategy 決定是否保留已在最新原始目錄中消失的數據。
     - archive（預設）：自最新原始目錄消失的 Turn 在 `data/1-sessions/` 中予以保留，並重新標記 `missing: true`；該 Turn 的 `visibilityFlag` 與 `prompt2` 不予變更。
     - mirror：來源刪除即觸發本地同步刪除。
   - **產出**：產出包含內容與預設 `visibilityFlag: true` 的 Session JSON；**不寫入 `title` 欄位**，標題依需求由可見 Turn 動態推導（見 §2.1 Session）。
2. **sessionsDir -> turnsMdDir (快取預渲染)**
   - **Renderer** 將每一輪 Turn 渲染為單獨的 Markdown 快取，供 UI 顯示使用。
   - 確保 UI 預覽與最終匯出使用相同的渲染引擎。
3. **sessionsDir -> topicsDir (主題管理與標題維護)**
   - **主題管理規則**：
     - 使用者在 UI 中多選 Session 並指派至自訂 Topic。
     - **排序彈性**：在 Topic 內可手動調整 Session 順序。
     - **解散與移動**：刪除 Topic 僅解除邏輯關聯；底層 Session 不會被刪除。
   - **動態標題**：Session 標題每次讀取時皆由 Turn 重新推導（見 §2.1）；使用者編輯 `prompt2` 或切換可見性後，無需另行寫入標題，下次讀取即反映新值。
   - 產出 Topic 後設資料 JSON，建立實體資料間的邏輯映射。
4. **topicsDir -> exportsDir (最終物理合併)**
   - **Exporter** 依據 Topic 定義順序，抓取實體快取檔案進行合併產出。
   - 僅合併 `visibilityFlag` 為 `true` 的 Turn，產出符合範本規則的最終文件。

#### 2.4 UI 互動規則

- **即時回饋**：`visibilityFlag` 的變更須立即反映於 UI。
- **缺失輪次過濾**：Session 視圖提供「Hide missing turns」開關，勾選時隱藏 `missing: true` 的 Turn。預設關閉（顯示缺失 Turn）。`missing` 欄位在 UI 中為唯讀；僅 Parser 在 `archive` 模式下執行兩代比對時設定。
- **Session 自動隱藏**：當「Hide hidden turns」過濾器開啟時，所有 Turn 的 `visibilityFlag` 皆為 false 的 Session 須從側邊欄與搜尋結果中隱藏；過濾器關閉時（預設），該類 Session 仍保持顯示，其 `visibleCount/turnCount` 計數會清楚反映此狀態。
- **批次選取**：支援批次選取 Session 進行 Topic 分類。
- **整理動作**：使用者明確觸發匯出動作。
  - UI 須在產出文件前要求確認。
  - **全局鎖定**：匯出動作執行期間，**Node.js Bridge** 必須阻塞所有對 1-sessions/ 與 3-topics/ 的寫入請求，防止資料競態。
- **Topic 排序**：Topics 面板依各 Topic 成員 Session 中**最新的 `endTime`** 排序；無成員的 Topic 退回其自身 `created` 時間。使用者透過 `Time ↑/↓` 控件切換升降序。
- **Topic 內 Session 順序**：在側邊欄各 Topic 之巢狀 Session 清單中，Session 始終以 `beginTime` 由舊至新顯示，與全域 Session 排序方向無關。
- **過濾器預設值**：三個過濾開關 ──「Hide hidden turns」「Hide missing turns」「MD preview」── 預設皆為勾選狀態，使首次瀏覽即呈現最簡潔的視圖。
- **Edit prompt2 對話框**：開啟 prompt2 編輯器時，若 `prompt2` 非空則預填其值，否則預填原始 `prompt`。清空欄位後儲存即得空 `prompt2`（亦即恢復顯示原始 `prompt`）。
- **Metrics 對話框**：「Show Metrics」動作會開啟對話框，彙整資料集 ── Topics 總數、Sessions（含完全隱藏者計數）、Turns（含隱藏與缺失計數）。狀態列不顯示這些彙整數值。

### 3. Design (設計) — 「系統如何架構？」

#### 3.1 核心組件職責

- **Node.js Bridge**：負責 IPC 通訊、UI Server、Global Write Lock、以及**輕量級狀態更新**（Flag/Prompt2/Title）。
- **Python Processing Core**：
  - **Parser (`parser.py`)**：負責多路原始目錄掃描、兩代差異比對與結構化數據初步生成。
  - **Topic Manager (`topic_mgr.py`)**：負責 Topic 的 CRUD 操作與 `updated` 時間戳更新。
  - **Renderer (`render_md.py`)**：負責增量渲染 Markdown 快取。
  - **Exporter (`exporter.py`)**：合併實體快取並套用範本。
- **前端 UI** (`ui/public/index.html`、`ui/public/main.js`)：實作畫面佈局、側邊欄與細節面板，以及 §2.4 所定義之所有 UI 互動規則 —— 逐輪可見性切換、過濾開關與其預設勾選狀態、Topic 與 Session 排序、批次選取、Edit `prompt2` 對話框、Metrics 對話框、整理動作確認流程。

#### 3.2 資料目錄結構

系統目錄形成一條清晰的知識轉換管線。

##### 目錄階層

```
data/
├── 0-raw/           原始 JSON 資料夾 (rawDir)
├── 1-sessions/      結構化 JSON (sessionsDir)
├── 2-turns_md/      逐 Turn MD 快取 (turnsMdDir)
├── 3-topics/        主題定義 JSON (topicsDir)
└── 4-exports/       最終匯出 Markdown (exportsDir)
```

##### 目錄角色定義

| 目錄 | 主要所有者 | 可變性 | 觸發時機 |
| :---- | :---- | :---- | :---- |
| `data/0-raw/` | 使用者 | 唯讀 | 初始導入數據 |
| `data/1-sessions/` | Parser / Bridge | 狀態可變 | 解析導入 + UI 狀態(Flag/Prompt2)切換 |
| `data/2-turns_md/` | Renderer | 內容不可變 | 內容變動或啟動同步 |
| `data/3-topics/` | Topic Manager | 高可變 | 使用者調整主題/順序時 |
| `data/4-exports/` | Exporter | 唯讀產物 | 執行「整理動作」後產出 |

#### 3.3 執行流程

1. **啟動 (Startup)**
   - **Node.js Bridge** (`bridge.js`) 啟動 App，讀取 `sync_config.yaml`，驗證 `data/` 目錄完整性。
   - Bridge 呼叫 **Parser** (`parser.py`)。Parser 對 Gemini Apps YYMMDD 目錄排序，執行兩代比對，更新 `data/1-sessions/`。
   - Bridge 呼叫 **Renderer** (`render_md.py`) 執行增量快取更新。**Renderer** 比對 `data/1-sessions/` 的修改日期與 `data/2-turns_md/` 中的既有快取，執行增量渲染以確保 UI 內容為最新。
2. **載入 UI**
   - Bridge 從 `data/1-sessions/` 讀取 Session 列表，過濾所有 Turn 均不可見的 Session。
   - Bridge 從 `data/3-topics/` 讀取 Topic 階層。
   - 前端透過 API 取得列表，並以 `sessionId` 讀取對應 `.md` 快取即時顯示。
3. **互動與管理**
   - **可見性切換**：使用者切換開關；Bridge 立即更新 `visibilityFlag`。若 Session 變為隱藏，UI 立即移除。
   - **Topic 指派**：使用者批次指派 Session 時，Bridge 呼叫 **Topic Manager** (`topic_mgr.py`) 更新 Topic JSON。
   - **動態標題**：使用者編輯 `prompt2` 或切換可見性時，Bridge 僅修改受影響的 Turn 欄位；Session 標題在下次讀取時由可見 Turn 重新推導，無需另行寫入。
4. **最終匯出**
   - 啟動全局鎖。Bridge 確認選取範圍（Topic 或 Session）。
   - Bridge 呼叫 **Exporter** (`exporter.py`) 依邏輯順序從 `data/2-turns_md/` 抓取實體檔案，執行物理合併，結果輸出至 `data/4-exports/`。

### 4. Coding (實作規範)

#### 4.1 關鍵開發準則

- **無損原則**：`0-raw/` 下的原始資料絕不可被修改。
- **MD 為顯示基準**：UI 必須讀取生成的 `.md` 檔案。
- **增量更新**：渲染引擎檢查雜湊或日期以避免冗餘工作。

#### 4.2 實作工具

- **Node.js**：使用 `child_process.spawn` 呼叫 Python。
- **Python**：使用 `pathlib` 與 `jinja2` 引擎。

#### 4.3 安全與健壯性

- **防禦數據競態**：匯出任務進行期間，Node.js Bridge 須阻塞所有寫入請求。
- **阻塞控制**：處理期間提供進度回饋。
- **增量安全**：執行兩代比對更新時，必須保留本地使用者的編輯狀態（Prompt2/Flag）。
- **檔案命名**：使用唯一 ID 作為檔名，避免特殊字元造成衝突。

#### 4.4 Topic 實作細節

- **ID 生成**：建議格式 `topic_YYYYMMDD_random`。
- **層級標題**：Topic 匯出時，Session 標題降階為 `## Session: [Title]`。
