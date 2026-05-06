# Gemini Chat Organizer RSDC Specification Document

This document defines the development framework for the "Gemini Chat Organizer," aimed at transforming raw AI conversations into structured, high-value knowledge documents.

## 1. Requirements — "What problems are we solving?"

### 1.1 Target Users

- Professional users who frequently interact with Gemini and need to turn conversation content into reports, notes, or development logs.
- Users who want to preserve and manage all AI history records locally.

### 1.2 Core Vision

- Eliminate noise from conversations, elevating AI dialogue from a "procedural tool" to a "knowledge asset," and provide full-process digital provenance.

### 1.3 Current Pain Points

- **Excessive Procedural Noise**: Conversations contain repeated error-correction cycles and retries, blurring the focus.
- **Lack of Local Backup**: Cloud conversation search is inconvenient, and once deleted a conversation cannot be recovered.
- **Missing Metadata**: Exported text lacks precise prompt timestamps, making it hard to reconstruct the line of thought.

### 1.4 System Goals

- **Full Download and Backup**: Mirror cloud conversations to a local path under a "local-first" storage model.
- **Precise Filtering**: Provide an interface for filtering (hide/show) specific conversation turns.
- **Context Preservation**: Mandatory recording of the date and timestamp for every conversation turn.
- **Standardized Output**: Final results convert into standard Markdown.

### 1.5 Topic Aggregation

- **Fragmentation Problem**: Address the issue of auto-segmented Sessions being scattered by interruptions.
- **Management Dimension**: Elevate to a "project / knowledge-point management" dimension.

## 2. Specification — "What are the rules of the system?"

### 2.1 Data Hierarchy

#### Data - topic

**Definition**: A logical container, manually created by the user, that aggregates one or more Sessions.

**Syntax**

```
topic = {topicId, name, description, sessionIds, tags, created, updated, beginTime, endTime}
sessionIds = [sessionId]
```

**Fields**

- `sessionIds`: Ordered list that determines the order of Sessions on export.
- `updated`: Whenever a Topic is changed (Session added/removed, reordered, name modified), the system must update this timestamp automatically.
- `beginTime` / `endTime`: Aggregate window over the Topic's member Sessions — `beginTime` = `min(session.beginTime)`, `endTime` = `max(session.endTime)`. Recomputed (and persisted) whenever Sessions are added/removed or the underlying Sessions' time ranges change. Both are `null` for an empty Topic.

#### Data - archive

**Definition**: The top-level data container, storing all Topics together with uncategorized Sessions.

#### Data - session

**Definition**: A chain of conversation topics continuous in semantics or in time.

**Syntax**

```
session = {sessionId, beginTime, endTime, turns}
turns = [turn]
```

**Fields**

- `sessionId`: Unique identifier.
- `beginTime` / `endTime`: Start and end time of the Session.

A Session has no stored title; the title is **always derived** from the Turns. Rule: the first Turn whose `visibilityFlag` is `true` provides the title — its `prompt2` if set, otherwise its `prompt` (first line, truncated to 20 chars). If no Turn is visible, fall back to the first Turn's `prompt2` / `prompt` so the Session still has a recognizable name. The title is computed on every read and is **never persisted to `data/1-sessions/*.json`**.

#### Data - turn

**Definition**: The smallest logical interaction unit in the system.

**Syntax**

```
turn = {turnId, timestamp, timestampUtc, kind, prompt, prompt2, response, attachments, visibilityFlag, missing}
```

**Fields**

- `timestamp`: Local-time display field. Governs the `YYYY-MM-DD HH:mm:ss` format rule; shown in Markdown exports.
- `timestampUtc`: Verbatim Takeout value. Canonical ordering key; used to derive `turnId` (`T{unix_seconds}`) and to compute gaps for Session segmentation.
- `kind`: Distinguishes conversation types (e.g., prompted).
- `prompt`: Original prompt text from Takeout. Immutable.
- `prompt2`: User-editable annotation/secondary prompt. When non-empty: the rendered turn Markdown emits an additional `Prompt2` block after the `Prompt` block (the original `prompt` is preserved verbatim). Also feeds the Session-title derivation rule (see Session above). Defaults to empty string.
- `response`: The AI reply content.
- `attachments`: List of attachment file names (e.g., images).
- `visibilityFlag`: Controls whether this Turn participates in display and export.
- `missing`: Boolean. Set to `true` only by the Parser, when a Turn that exists in the second-newest raw directory has disappeared from the newest one and `syncStrategy` is `archive`. Defaults to `false`. Independent of `visibilityFlag` — the user's prior visibility/`prompt2` choices are preserved.

**Naming and Data-Structure Rules**

- **Timestamp Format**: Uniformly use the `YYYY-MM-DD HH:mm:ss` format.
- **State Attributes**: Each Turn must carry a `visibilityFlag` (Boolean) and a `timestamp` attribute.

### 2.2 Configurations

System behavior and the data flow (Artifacts) are governed by two core YAML files:

#### Config - sync_config.yaml

Defines system paths, data mappings, and parsing rules.

```yaml
rawDir: "data/0-raw"
sessionsDir: "data/1-sessions"
turnsMdDir: "data/2-turns_md"
topicsDir: "data/3-topics"
exportsDir: "data/4-exports"
sessionGapSeconds: 1800
syncStrategy: "archive" # archive: local data preserved after source deletion; mirror: sync-delete
```

**Field and Artifact definitions:**

- **`rawDir` (Raw Source)**: Raw data root directory. Contains one or more `Gemini Apps YYMMDD` subdirectories (one per Takeout export); the Parser scans them for the two-generation diff. The system treats it as read-only. Legacy fallback: if `rawDir` itself contains the activity JSON (no matching subdirectories), the Parser performs a full single-directory parse.
- **`sessionsDir` (Processed JSON)**: Structured data directory. Stores the Session JSON produced by the Parser; the Bridge writes user state (Flag/Prompt2). This is the system's "state core," carrying both content and `visibilityFlag`.
- **`turnsMdDir` (UI MD Cache)**: Markdown cache directory. Per-Turn Markdown files emitted by the Renderer for UI display.
- **`topicsDir` (Topic Metadata)**: Topic definition directory. Stores user-defined Topic JSON, building logical mappings between Sessions.
- **`exportsDir` (Final Artifact)**: Export directory. Where the final merged Markdown documents are stored.
- **`sessionGapSeconds`**: Segmentation threshold. If two adjacent interactions are separated by more than this many seconds, they are treated as a new Session.
- **`syncStrategy`**: Sync strategy. `archive` (default): local data preserved after source deletion; `mirror`: sync-delete.

#### Config - export_template.yaml

Defines the layout, appearance, and naming rules used by the Exporter when producing the final document.

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

The data-transformation pipeline within the system, and the logic embedded at each stage:

1. **`rawDir` -> `sessionsDir` (Two-Generation Diff Comparison and Update)**
   - **Naming Recognition**: `parser.py` identifies subdirectories matching the Gemini Apps YYMMDD naming convention.
   - **Incremental Comparison**: The system parses subdirectory dates and selects the **two most recent subdirectories** for content comparison.
   - **Diff Identification**: Using the "newest subdirectory" as the baseline, compare against the "second-newest" to identify new Turns, edited content, or deleted conversations.
   - **Fallback**: If only a single raw directory exists, perform a full-parse import of that directory.
   - **State Merge**: Merge identified incremental data into existing Session JSON in `sessionsDir`, ensuring `timestampUtc` as the unique key. Must **not overwrite** locally existing `prompt2` or `visibilityFlag` values.
   - **Deletion Handling (syncStrategy)**:
     - archive (default): If conversations disappear from the newest raw directory (relative to the second-newest), the corresponding Turns are preserved in `data/1-sessions/` and re-tagged with `missing: true`. Their `visibilityFlag` and `prompt2` are not touched.
     - mirror: Source deletion triggers local sync-deletion.
   - Emit Session JSON containing the content and a default `visibilityFlag: true`. **No `title` field is written**; the title is computed on demand from the visible Turns (see §2.1 Session).
2. **`sessionsDir` -> `turnsMdDir` (Cache Pre-Rendering)**
   - Read Session state and render each conversation Turn into an independent Markdown cache file.
   - Ensure that the UI preview and the final export use the same rendering engine.
3. **`sessionsDir` -> `topicsDir` (Topic Management and Assignment)**
   - **Topic Management Rules**:
     - The user multi-selects Sessions in the UI and assigns them to a custom Topic.
     - **Reordering Flexibility**: Within a Topic, the user can manually adjust Session ordering.
     - **Dissolution and Movement**: Deleting a Topic only releases the logical association; the underlying Sessions are not deleted.
   - **Dynamic Title**: The Session title is derived on every read from its Turns (see §2.1) — there is nothing to write back when the user edits `prompt2` or toggles visibility; the next read returns the new value.
   - Emit Topic Metadata JSON, building the logical mapping between physical data.
4. **`topicsDir` -> `exportsDir` (Final Physical Merge)**
   - Pull Markdown cache files from `turnsMdDir` in the order specified by the Topic definition and merge them.
   - Merge only Turns whose `visibilityFlag` is `true`, producing a final document that conforms to the template rules.

### 2.4 UI Interaction Rules

- **Per-turn Visibility**:
  - The user can toggle visibility for an individual Turn.
  - The system must update that Turn's `visibilityFlag` immediately and reflect the change in the UI preview at once.
- **Missing-turn Filter**:
  - The Session view provides a "Hide missing turns" toggle that filters out Turns whose `missing` flag is `true`. Default is off (missing Turns are shown). The flag is read-only in the UI; it is set only by the Parser during two-generation diff in `archive` mode.
- **Session Auto-hide Logic**:
  - When the "Hide hidden turns" filter is on, Sessions whose every Turn has `visibilityFlag: false` are also hidden from the sidebar and search results.
  - When the filter is off (default), such Sessions remain visible; their `visibleCount/turnCount` meta makes the state self-evident.
- **Batch Select**: Supports batch selection of Sessions for Topic categorization.
- **Organize Action**: The user explicitly triggers the export action.
  - The UI must request confirmation before producing the document.
  - **Global Lock**: During execution the UI enters a locked state, **prohibiting all write operations** (including visibility toggles and Topic changes), to avoid data races.
- **Topic Expansion**: Each Topic row in the Topics panel can be clicked to toggle showing its nested Session list; clicking also navigates to the Topic detail view. The panel header has an Expand/Collapse control that toggles **all** Topics at once; its label reflects the inverse action (reads "Expand" when not every Topic is expanded, "Collapse" when every Topic is expanded). Initial state: every Topic is collapsed.
- **Topic Sort**: The Topics panel sorts entries by `topic.endTime` (i.e., the maximum `endTime` across the Topic's member Sessions, persisted on the Topic — see §2.1). Each row also displays this `endTime` (date portion) as a secondary line below the Topic name; when `endTime` is `null` (empty Topic), the displayed time is blank. For ordering, empty Topics fall back to `topic.created` so they remain comparable. The user toggles ascending/descending via a `Time ↑/↓` control.
- **Session Order within a Topic**: Inside each Topic's nested session list (sidebar), Sessions are always shown oldest first by `beginTime`, independent of the global Session sort direction.
- **Filter Defaults**: The three filter toggles — *Hide hidden turns*, *Hide missing turns*, *MD preview* — are checked by default, so the first-time view is the cleanest representation.
- **Edit prompt2 Dialog**: Opening the editor pre-populates the input with the current `prompt2` if non-empty, otherwise with the original `prompt`. Clearing the field saves an empty `prompt2` (i.e., reverts to displaying the original `prompt`).
- **Metrics Dialog**: A "Show Metrics" action opens a dialog summarising the dataset — total Topics, Sessions (with the count of fully-hidden ones), and Turns (with hidden and missing counts). The status bar does not display these aggregates.

## 3. Design — "How is the system architected?"

### 3.1 Core Component Responsibilities

- **Node.js Bridge**: Responsible for entry-point management, providing the UI Server, performing IPC with the Python core, lifecycle monitoring, and **lightweight state updates** (visibilityFlag / prompt2 / title). **Must enforce the Global Write Lock during exports**.
- **Python Processing Core**:
  - **Parser (`parser.py`)**: Scans multiple raw directories, performs two-generation diff comparison, and generates initial structured data.
  - **Topic Manager (`topic_mgr.py`)**: Handles Topic CRUD operations and ensures the `updated` timestamp is refreshed on every change.
  - **Renderer (`render_md.py`)**: Reads Session JSON and performs incremental Markdown cache rendering.
  - **Exporter (`exporter.py`)**: Reads export requests, merges visible MD cache files in Topic / Session order, and produces the final artifact.
- **Front-end UI** (`ui/public/index.html`, `ui/public/main.js`): Implements the layout, sidebar/detail panes, and all of the UI Interaction Rules in §2.4 — per-turn visibility toggles, filter toggles and their default-checked state, Topic and Session sort, batch select, Edit `prompt2` dialog, Metrics dialog, and the Organize confirmation flow.

### 3.2 Directory Structure

The system directories form a clear knowledge-transformation pipeline. The table below defines each directory's physical location, ownership, and lifecycle.

#### Directory Hierarchy

```
data/
├── 0-raw/           Raw JSON folder (rawDir)
├── 1-sessions/      Structured JSON (sessionsDir)
├── 2-turns_md/      Per-Turn MD cache (turnsMdDir)
├── 3-topics/        Topic definition JSON (topicsDir)
└── 4-exports/       Final exported Markdown (exportsDir)
```

#### Directory Role Definitions

| Directory | Primary Owner | Mutability | Trigger |
| :---- | :---- | :---- | :---- |
| `data/0-raw/` | User | read-only | initial data import |
| `data/1-sessions/` | Parser / Bridge | mutable state | initial parse + UI state toggles (Flag/Prompt2) |
| `data/2-turns_md/` | Renderer | immutable content | on content change or startup cache sync |
| `data/3-topics/` | Topic Manager | highly mutable | when the user defines/adjusts Topics |
| `data/4-exports/` | Exporter | read-only artifact | after the user runs the "Organize Action" |

### 3.3 Execution Flow

This section defines the key steps from system startup to export, along with the interactions between components.

1. **Startup**
   - The **Node.js Bridge** launches the App, reads `sync_config.yaml`, and verifies the integrity of the `data/` directory.
   - If new data is detected, the **Node.js Bridge** invokes the **Parser (`parser.py`)**. The Parser sorts directories by date, locks onto the two most recent Gemini Apps YYMMDD directories, analyzes differences, and updates `data/1-sessions/`.
   - The **Node.js Bridge** invokes the **Renderer (`render_md.py`)** for incremental cache update.
2. **Pre-rendering**
   - The **Node.js Bridge** invokes the **Renderer (`render_md.py`)**.
   - The **Renderer** compares the modification dates of `data/1-sessions/` against the existing cache in `data/2-turns_md/` and runs incremental rendering to ensure the UI content is up to date.
3. **UI Loading**
   - The **Node.js Bridge** reads the Session list from `data/1-sessions/`, filtering out Sessions whose every Turn is invisible.
   - The **Node.js Bridge** reads the Topic hierarchy from `data/3-topics/`.
   - The frontend (UI) fetches the list via API and reads the corresponding `.md` cache directly by `sessionId` for instant display.
4. **Interaction & Management**
   - **Visibility Change**: The user toggles a switch; the **Node.js Bridge** immediately updates the `visibilityFlag` in `data/1-sessions/`. If a Session becomes hidden, the UI removes it from the list immediately.
   - **Topic Assignment**: When the user batch-assigns Sessions, the **Node.js Bridge** invokes the **Topic Manager (`topic_mgr.py`)** to update the Topic JSON under `data/3-topics/`.
   - **Dynamic Title**: When the user edits `prompt2` or toggles visibility, the Bridge writes the affected Turn fields; the Session title is recomputed on the next read from the visible Turns and needs no separate write.
5. **Final Export**
   - The user clicks export; the **Node.js Bridge** confirms the selected scope (Topic or Session).
   - The **Node.js Bridge** invokes the **Exporter (`exporter.py`)**, which pulls physical files from `data/2-turns_md/` in logical order, performs the physical merge, and emits the result into `data/4-exports/`.

## 4. Coding

### 4.1 Key Development Principles

- **MD as the Display Source of Truth**: The UI must read the generated `.md` files.
- **Incremental Update**: The rendering engine must check hashes or dates to avoid redundant work.
- **Lossless Processing**: Raw data under `0-raw/` must never be modified.

### 4.2 Implementation Tools

- **Node.js**: Use `child_process.spawn` to invoke Python.
- **Python**: Use `pathlib` and the `jinja2` engine.

### 4.3 Security and Robustness

- **Defense Against Data Races**: While an export task is in progress, the Node.js Bridge must block all write requests.
- **File Naming**: Use unique IDs as filenames to avoid conflicts caused by special characters.
- **Blocking Control**: Provide progress feedback during processing.
- **Incremental Safety**: During two-generation diff comparison, the system must ensure it does not overwrite user-edited `prompt2` or `visibilityFlag` values.

### 4.4 Topic Implementation Details

- **ID Generation**: Recommended pattern `topic_YYYYMMDD_random`.
- **Hierarchical Headers**: When exporting a Topic, Session titles demote to a second-level header (`## Session: [Title]`).
