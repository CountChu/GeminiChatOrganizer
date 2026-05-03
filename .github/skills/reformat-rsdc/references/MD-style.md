# Markdown style

When creating or editing Markdown files in this repo:

- Use `-` for unordered list items, not `*`.
- Do not wrap header text in `**` (headers are already styled by their `#` level).
- In headers, write numbered prefixes plainly as `1. name` — do not escape the period as `1\. name`.
- Wrap directory trees, ASCII diagrams, and other preformatted blocks in a fenced code block so characters like `#` and `_` render literally and don't need backslash escapes.

## Transforms applied by reformat_tw.py

The reformat script ([.github/skills/reformat-rsdc/references/scripts/reformat_tw.py](./scripts/reformat_tw.py)) operationalizes the rules above through these transforms, in order:

1. Strips Markdown trailing two-space hard-break sequences from every line.
2. Detects whether the input is a raw Word/Docs paste — looks for `**`-wrapped headers, `\.` escapes, `\-` escapes in headers, or `*` bullets. If none are present, the file is already clean and the script enters idempotent-only mode (skip transforms 3–7; just inline-code missed identifiers in body text). This makes re-running on a clean file a true no-op.
3. **Headers**: strips surrounding `**…**`, unescapes `\.` and `\-` in titles, then shifts heading levels down by one (so the source's `# 1. Requirements` becomes `## 1. Requirements`) — except the very first `#` line, which stays as the document title.
4. **Bullets**: converts every line-leading `*` to `-` (preserves `**bold**` and `*` inside YAML strings).
5. **De-escapes body text**: `\-` → `-`, `\_` → `_`, `\#` → `#`, `\[` → `[`, `\]` → `]`, `\>` → `>`, `\*` → `*`, `\=` → `=`, `\+` → `+`, `\\n` → `\n`.
6. **Wraps preformatted blocks in fenced code blocks**:
    - `**Syntax**` body → plain ` ``` ` fence.
    - `**Example**` body → ` ```json ` fence.
    - YAML config block under `#### Config - <name>.yaml` (contiguous `key: value` lines after the description paragraph) → ` ```yaml ` fence.
    - Directory tree starting with a `data/` line followed by `├──`/`└──` lines → plain ` ``` ` fence.
    - Each handler skips wrapping if the block is already fenced (the next non-blank line is ` ``` `), so partial-clean inputs aren't double-wrapped.
7. **Inline-codes a fixed list of identifiers** in body text only (skipped inside fences and inside header lines): field names (`visibilityFlag`, `timestamp`, `timestampUtc`, `sessionId`, `topicId`, `turnId`, `beginTime`, `endTime`, `sessionIds`), modules (`parser.py`, `topic_mgr.py`, `render_md.py`, `exporter.py`), configs (`sync_config.yaml`, `export_template.yaml`), tools (`pathlib`, `jinja2`, `child_process.spawn`), paths (`data/0-raw/`, `data/1-sessions/`, `data/2-turns_md/`, `data/3-topics/`, `data/4-exports/`, `0-raw/`), config keys (`rawDir`, `sessionsDir`, `turnsMdDir`, `topicsDir`, `exportsDir`, `sessionGapSeconds`).
