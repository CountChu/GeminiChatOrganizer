---
name: sync-rsdc
description: "Regenerate docs/GeminiChatOrganizer-RSDC.md (English mirror) from docs/GeminiChatOrganizer-RSDC-tw.md."
---

# MUST FOLLOW

- Must run workflow step by step, and display each step number.
- Touch only the two RSDC files. Do NOT modify CLAUDE.md, the Pydantic models, the YAML configs, or any source code — even if their content disagrees with the spec.
- Never translate identifiers, paths, YAML keys, YAML values, or schema field names. Only Chinese prose translates.

# Workflow

## Step 0 - Warmup

- Confirm the TW file exists. Bail out immediately if it doesn't — there is nothing for the workflow to operate on:
  ```bash
  test -f docs/GeminiChatOrganizer-RSDC-tw.md \
    || { echo "error: docs/GeminiChatOrganizer-RSDC-tw.md not found" >&2; exit 1; }
  ```

- Confirm the EN file exists. Bail out immediately if it doesn't — Step 1 rewrites it, so a missing file is a setup error worth catching up front:
  ```bash
  test -f docs/GeminiChatOrganizer-RSDC.md \
    || { echo "error: docs/GeminiChatOrganizer-RSDC.md not found" >&2; exit 1; }
  ```

## Step 1 - Sync EN to TW

- Read the current EN file [docs/GeminiChatOrganizer-RSDC.md](../../../docs/GeminiChatOrganizer-RSDC.md) end-to-end first, so translation choices stay consistent with prior naming.

- Rewrite [docs/GeminiChatOrganizer-RSDC.md](../../../docs/GeminiChatOrganizer-RSDC.md) so its structure mirrors the freshly-cleaned TW exactly, with English prose.

- The sync applies these mirroring rules:
  1. **Same heading hierarchy**: identical count of `##`/`###`/`####` sections in identical order with parallel English titles. Drop the Chinese parenthetical translations like `(Target Users)` — EN doesn't need them.
  2. **Same code fences**: byte-identical YAML configs and Syntax blocks (don't translate identifiers/paths/YAML inside fences). Inside the §3.2 directory tree, only translate the inline path comments (e.g. "原始 JSON 資料夾 (對應 rawDir)" → "Raw JSON folder (rawDir)").
  3. **Same camelCase schema** in field lists: `topicId`, `sessionId`, `turnId`, `beginTime`, `endTime`, `visibilityFlag`, `timestampUtc`, `sessionIds`, `created`, `updated`. Never translate.
  4. **Same table** in §3.2 "目錄角色定義": same rows, same column count. Translate only column headers ("目錄"→"Directory", "主要所有者"→"Primary Owner", "可變性"→"Mutability", "觸發時機"→"Trigger") and trigger-cell descriptions; path cells stay literal in backticks.
  5. **Same numbered-list structure** in §2.3 Data Flow and §3.3 Execution Flow — same step count, same nested bullet count.
  6. **Same JSON sample values** if a `Data - topic` Example block is present (preserve Chinese `name` field verbatim — sample data, not prose).

- Use this translation glossary for consistency across runs:

  | TW | EN |
  | :---- | :---- |
  | 需求 / 規格 / 設計 / 實作規範 | Requirements / Specification / Design / Coding |
  | 解決什麼問題？/ 系統的規則是什麼？/ 系統如何架構？ | What problems are we solving? / What are the rules of the system? / How is the system architected? |
  | 使用者對象 / 核心願景 / 現狀痛點 / 系統目標 / 主題聚合需求 | Target Users / Core Vision / Current Pain Points / System Goals / Topic Aggregation |
  | 對話單元 / 輪次 / 封存區 | Session / Turn / Archive |
  | 過程性提問 / 過程雜訊 | procedural prompts / procedural noise |
  | 增量更新 / 無損處理 | incremental update / lossless processing |
  | 可見性切換 / 多選模式 / 整理動作 / 鎖定狀態 | visibility toggle / batch select / organize action / locked state |
  | 資料目錄結構 / 目錄層級圖 / 目錄角色定義 | Directory Structure / Directory Hierarchy / Directory Role Definitions |
  | 執行流程 / 啟動 / 預渲染 / 載入 UI / 狀態變更 / 最終導出 | Execution Flow / Startup / Pre-rendering / UI Loading / State Change / Final Export |
  | 命名與數據結構規範 / 配置規範 | Naming and Data-Structure Rules / Configurations |
  | 數據解析與自動切分 / 快取預渲染 / 主題管理與歸位 / 最終物理合併 | Parsing and Auto-Segmentation / Cache Pre-Rendering / Topic Management and Assignment / Final Physical Merge |
  | Session 推論規則 / 自動標題生成 / 排序靈活性 / 解散與移動 | Session Inference Rule / Automatic Title Generation / Reordering Flexibility / Dissolution and Movement |
  | 核心組件職責 / 關鍵開發準則 / 安全與健壯性 | Core Component Responsibilities / Key Development Principles / Security and Robustness |
  | 檔案命名 / 阻塞控制 / 層級標題 / ID 生成 | File Naming / Blocking Control / Hierarchical Headers / ID Generation |

- Verify section parity and style:
  ```bash
  grep -cE '^### '  docs/GeminiChatOrganizer-RSDC.md docs/GeminiChatOrganizer-RSDC-tw.md
  grep -cE '^#### ' docs/GeminiChatOrganizer-RSDC.md docs/GeminiChatOrganizer-RSDC-tw.md
  grep -nE '[0-9]\\\.|^\s*\*\s|^#+ \*\*|\\[-_#\[\]>+]' docs/GeminiChatOrganizer-RSDC.md
  ```
  First two: counts must match between EN and TW. Third: must return zero matches.

- Display a sync summary:
  - **File**: `docs/GeminiChatOrganizer-RSDC.md`.
  - **Section parity**: `###` count and `####` count for both files (must match).
  - **Style greps**: zero matches expected on the EN style check.
  - **Structural changes flowed from TW**: list any new sub-sections / steps / table rows now present in EN that weren't there before this run.

# Prompt Examples

## Prompt 1

```
What skills do you have?
```

## Prompt 2

```
/sync-rsdc
```

## Prompt 2

```
TW only — I'll review before you touch EN.
```

(Skip Step 1; after Step 0, end with a one-line offer: "TW reformatted; EN is now stale — want me to sync it too?")

# Prompts for Developing

## Prompt 1

```
Show me the diff between the new EN and the prior EN, grouped by section, so I can spot any wording I want to revert.
```

## Prompt 2

```
Re-run /sync-rsdc but this time use "Owner" instead of "Primary Owner" in the §3.2 table header. Update the glossary in SKILL.md too.
```

## Prompt 3

```
The TW now has a new §2.5 — make sure /sync-rsdc creates the matching §2.5 in EN and add the term to the glossary.
```

## Prompt 4

```
Add a new style grep to the verification step: catch lines that look like a header followed by trailing whitespace.
```

## Prompt 5

```
Extend reformat_tw.py to also fence ASCII flow diagrams (lines containing `→` between identifier-like tokens).
```
