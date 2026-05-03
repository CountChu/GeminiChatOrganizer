---
name: sync-rsdc
description: "Reformat docs/GeminiChatOrganizer-RSDC-tw.md (Traditional Chinese, the authored source) to follow CLAUDE.md's Markdown style rules
---

# MUST FOLLOW

- Must run workflow step by step, and display each step number.
- Touch only the two RSDC files. Do NOT modify CLAUDE.md, the Pydantic models, the YAML configs, or any source code — even if their content disagrees with the spec.
- Preserve the user's additions verbatim (new sub-sections, new numbered steps, new table rows). Reformat them; never drop or merge.
- Never translate identifiers, paths, YAML keys, YAML values, or schema field names. Only Chinese prose translates.

# Workflow

## Step 0 - Warmup

- Confirm the TW file exists. Bail out immediately if it doesn't — there is nothing for the workflow to operate on:
  ```bash
  test -f docs/GeminiChatOrganizer-RSDC-tw.md \
    || { echo "error: docs/GeminiChatOrganizer-RSDC-tw.md not found" >&2; exit 1; }
  ```

- Read [references/MD-style.md](./references/MD-style.md) to anchor the rules in scope:
  - Use `-` for unordered list items, not `*`.
  - Do not wrap header text in `**`.
  - In headers, write numbered prefixes plainly (`1. name`), not escaped (`1\. name`).
  - Wrap directory trees, ASCII diagrams, and other preformatted blocks in fenced code blocks so characters like `#` and `_` render literally and don't need backslash escapes.

- Audit [reformat_tw.py](./scripts/reformat_tw.py) against the rules just anchored. Confirm each rule in [references/MD-style.md](./references/MD-style.md) has a corresponding transform in the script (`*` → `-` bullets, `**…**` header strip, `1\. ` → `1. ` un-escape, fenced code blocks for preformatted content). If a rule has no matching transform — or the script enforces a rule not in `MD-style.md` — stop and surface the gap before running Step 1. Do not edit the script in this skill; flag it for a separate change.

## Step 1 - Reformat TW

- Read the current TW file [docs/GeminiChatOrganizer-RSDC-tw.md](../../../docs/GeminiChatOrganizer-RSDC-tw.md) end-to-end first, so you can describe what changed after the script runs.

- Run the script [reformat_tw.py](./scripts/reformat_tw.py) to apply every Markdown-style transformation in one pass:
  ```bash
  python3 .claude/skills/sync-rsdc/scripts/reformat_tw.py docs/GeminiChatOrganizer-RSDC-tw.md
  ```
  - Argument is the path to the TW file. The script edits in place.
  - The script writes `reformatted <path>` to stdout and exits `0` on success, `1` if the file is missing, `2` on bad arguments.

- The script applies the seven transforms documented in [references/MD-style.md](./references/MD-style.md) ("Transforms applied by reformat_tw.py"). Skim them so you know what to expect in the diff, especially transform 2's idempotent-only mode for already-clean inputs and transform 7's fixed inline-code identifier list.

- After the script finishes, eyeball the diff for anything the script couldn't infer (a brand-new sub-section type, a Syntax block that uses an unfamiliar marker word, a custom code-ish identifier that isn't in the inline-code list). Hand-touch only those.

- Verify by running these greps; all should return zero matches:
  ```bash
  grep -nE '[0-9]\\\.' docs/GeminiChatOrganizer-RSDC-tw.md
  grep -nE '^\s*\*\s' docs/GeminiChatOrganizer-RSDC-tw.md
  grep -nE '^#+ \*\*' docs/GeminiChatOrganizer-RSDC-tw.md
  grep -nE '\\[-_#\[\]>+]' docs/GeminiChatOrganizer-RSDC-tw.md
  ```

- Display a reformat summary:
  - **File**: `docs/GeminiChatOrganizer-RSDC-tw.md`.
  - **Mode**: `raw` (full transform applied) or `clean` (idempotent-only — only inline-coding ran).
  - **Headers normalized**: count of `##`/`###`/`####` after rewrite.
  - **Bullets converted**: count of `-`-bullets after (was `*`-bullets in raw mode).
  - **Code fences added**: count of new ` ``` ` blocks (Syntax + YAML + tree + Example).
  - **Style greps**: each of the four verification greps with its match count (expected: 0).
  - **Structural changes vs prior version**: any new sub-sections, new steps, new table rows the user added in this re-paste. List them so Step 2 knows what to mirror.

# Prompt Examples

## Prompt 1

```
What skills do you have?
```

## Prompt 2

```
/sync-rsdc
```

## Prompt 3

```
I just re-pasted docs/GeminiChatOrganizer-RSDC-tw.md from Google Docs.
Run /sync-rsdc.
```

## Prompt 4

```
TW only — I'll review before you touch EN.
```

(Skip Step 2; after Step 1, end with a one-line offer: "TW reformatted; EN is now stale — want me to sync it too?")

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
