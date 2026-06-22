# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Repository status

The two-process architecture from §3 of the spec is implemented:

- [engine/](engine/) — Python core: `parser.py`, `topic_mgr.py`, `render_md.py`, `exporter.py`, plus `models.py` (pydantic), `ipc.py` (JSON-over-stdio), `cli.py`.
- [ui/](ui/) — Node.js bridge ([ui/server.js](ui/server.js), [ui/python_bridge.js](ui/python_bridge.js)) and browser front-end under [ui/public/](ui/public/).
- [data/](data/) — live working dataset under `0-raw/`, `1-sessions/`, `2-turns_md/`, `3-topics/`, `4-exports/`.
- [sync_config.yaml](sync_config.yaml) and [export_template.yaml](export_template.yaml) — the two configs from §2.2.
- [requirements.txt](requirements.txt) (Python deps) and [ui/package.json](ui/package.json) (Node deps).

The RSDC specification under [docs/](docs/) is the authoritative source for architecture and rules:

- [docs/GeminiChatOrganizer-RSDC.md](docs/GeminiChatOrganizer-RSDC.md) — English, authoritative.
- [docs/GeminiChatOrganizer-RSDC-tw.md](docs/GeminiChatOrganizer-RSDC-tw.md) — Traditional Chinese mirror. Keep both in sync when the spec changes.

Read the spec before making non-trivial changes — it constrains architecture, not just features.

## What the product does

Gemini Chat Organizer downloads a user's Gemini conversation history to disk, lets them hide/show individual turns through a UI, and exports a cleaned Markdown document. The point is to strip "procedural noise" (retries, error-correction back-and-forth) and preserve per-turn timestamps for provenance.

The data model is a strict hierarchy: **Archive → Topic → Session → Turn**. `Archive` is the top-level container; `Topic` is a user-created logical grouping that aggregates one or more Sessions (see [docs/GeminiChatOrganizer-RSDC.md](docs/GeminiChatOrganizer-RSDC.md) §2.1). A `Turn` is one `prompt` + one `response`, and every Turn carries a `visibilityFlag: bool` and a `timestamp` (format `YYYY-MM-DD HH:mm:ss`). Don't invent extra levels or flatten this.

## Architecture (planned)

Two processes, one repository on disk:

- **Node.js bridge** (`ui/`) — runs the UI, owns the Python subprocess lifecycle, handles hide/show clicks.
- **Python core** (`engine/`) — four roles: `Parser` (raw JSON → `Session`/`Turn` objects with auto-segmentation), `Topic Manager` (CRUD on Topics and Session-to-Topic mapping), `Renderer` (Session JSON → per-Turn Markdown cache via Jinja2), `Exporter` (visible MD cache + topic order + template → final Markdown).
- **Local repository** — `data/0-raw/` (downloaded JSON), `data/1-sessions/` (structured Session JSON with visibility state), `data/2-turns_md/` (per-Turn MD cache), `data/3-topics/` (Topic definition JSON), `data/4-exports/` (final `.md`).

Flow: Sync → `data/0-raw/` → Parser → `data/1-sessions/` → Renderer → `data/2-turns_md/` → UI → user toggles write to `data/1-sessions/` in real time → Topic Manager → `data/3-topics/` → Organize → Exporter reads cache + topic state + `export_template.yaml` → `data/4-exports/*.md`.

## Non-obvious rules from the spec (section 4)

These are the constraints most likely to be violated by default implementations — honor them:

- **IPC is JSON over stdio or a local socket.** Node ↔ Python must not share memory or touch each other's process space. Wrap all Python exceptions into a JSON error envelope before returning to Node.
- **No hardcoded paths in Python.** Node passes every path as a CLI argument when spawning the Python process. Python uses `pathlib`, never string paths or relative-path assumptions.
- **Python functions must be type-annotated** (`typing` module); data validation uses `pydantic`. Document generation uses `markdown-it` or `jinja2`.
- **Lock the UI while Exporter is reading.** `data/1-sessions/` is shared state; the spec calls out data-race prevention explicitly.
- **Two config files drive behavior** — `sync_config.yaml` (sync cadence, paths) and `export_template.yaml` (Markdown template: timestamp-in-header, line-break style, etc.). New knobs should land in one of these, not as code constants.
- **Visibility state must be persistent.** Toggling in the UI writes through to `data/1-sessions/` immediately — it's not an in-memory view filter.

## Markdown style

When creating or editing Markdown files in this repo, follow the rules in [.github/skills/reformat-rsdc/references/MD-style.md](.github/skills/reformat-rsdc/references/MD-style.md).
