# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository status

This repo is **spec-only**. There is no source code, package manifest, build system, or test suite yet. The only content is the RSDC specification under [docs/](docs/):

- [docs/GeminiChatOrganizer-RSDC.md](docs/GeminiChatOrganizer-RSDC.md) — English, authoritative.
- [docs/GeminiChatOrganizer-RSDC-tw.md](docs/GeminiChatOrganizer-RSDC-tw.md) — Traditional Chinese mirror. Keep both in sync when the spec changes.

Before scaffolding anything, read the spec in full — it constrains architecture, not just features.

## What the product does

Gemini Chat Organizer downloads a user's Gemini conversation history to disk, lets them hide/show individual turns through a UI, and exports a cleaned Markdown document. The point is to strip "procedural noise" (retries, error-correction back-and-forth) and preserve per-turn timestamps for provenance.

The data model is a strict three-level hierarchy: **Archive → Session → Turn**. A `Turn` is one `Prompt` + one `Response`, and every Turn carries a `visibility_flag: bool` and a `timestamp` (format `YYYY-MM-DD HH:mm:ss`). Don't invent extra levels or flatten this.

## Architecture (planned)

Two processes, one repository on disk:

- **Node.js bridge** (`ui/`) — runs the UI, owns the Python subprocess lifecycle, handles hide/show clicks.
- **Python core** (`engine/`) — three roles: `Downloader` (scrapes Gemini), `Parser` (raw → `Turn` objects), `Exporter` (state + template → Markdown).
- **Local repository** — `warehouse/raw/` (downloaded JSON), `warehouse/processed/` (with visibility state), `exports/` (final `.md`).

Flow: Sync → `warehouse/raw/` → Parser → UI → user toggles write to `warehouse/processed/` in real time → Organize → Exporter reads processed state + `export_template.yaml` → `exports/*.md`.

## Non-obvious rules from the spec (section 4)

These are the constraints most likely to be violated by default implementations — honor them:

- **IPC is JSON over stdio or a local socket.** Node ↔ Python must not share memory or touch each other's process space. Wrap all Python exceptions into a JSON error envelope before returning to Node.
- **No hardcoded paths in Python.** Node passes every path as a CLI argument when spawning the Python process. Python uses `pathlib`, never string paths or relative-path assumptions.
- **Python functions must be type-annotated** (`typing` module); data validation uses `pydantic`. Document generation uses `markdown-it` or `jinja2`.
- **Lock the UI while Exporter is reading.** `warehouse/processed/` is shared state; the spec calls out data-race prevention explicitly.
- **Two config files drive behavior** — `sync_config.yaml` (sync cadence, paths) and `export_template.yaml` (Markdown template: timestamp-in-header, line-break style, etc.). New knobs should land in one of these, not as code constants.
- **Visibility state must be persistent.** Toggling in the UI writes through to `warehouse/processed/` immediately — it's not an in-memory view filter.

## Markdown style

When creating or editing Markdown files in this repo:

- Use `-` for unordered list items, not `*`.
- Do not wrap header text in `**` (headers are already styled by their `#` level).
- In headers, write numbered prefixes plainly as `1. name` — do not escape the period as `1\. name`.
- Wrap directory trees, ASCII diagrams, and other preformatted blocks in a fenced code block so characters like `#` and `_` render literally and don't need backslash escapes.
