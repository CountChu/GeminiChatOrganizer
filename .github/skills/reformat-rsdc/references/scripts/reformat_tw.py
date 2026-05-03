"""Reformat docs/GeminiChatOrganizer-RSDC-tw.md to follow CLAUDE.md's Markdown style.

Mechanical, idempotent. Re-running on an already-clean file is a no-op.

Transformations:
  1. Strip Markdown hard-break trailing two-space sequences.
  2. Headers: strip surrounding `**...**`, unescape `\\.` and `\\-` in titles,
     shift heading levels down by 1 (so the source's `#` top section becomes `##`)
     except the very first `#` line, which stays as the document title.
  3. Bullets: line-leading `*` → `-`.
  4. Body: replace `\\-`, `\\_`, `\\#`, `\\[`, `\\]`, `\\>`, `\\*`, `\\=`, `\\\\n` with literals.
  5. Wrap preformatted blocks in fenced code blocks:
        - `**Syntax**` body → plain ``` fence
        - `**Example**` body → ```json fence
        - YAML config block under `#### Config - <name>.yaml` → ```yaml fence
        - directory tree starting with `data/` followed by `├──`/`└──` lines → plain fence
  6. Inline-code a fixed list of identifiers when they appear as standalone tokens
     in body text (skipped inside code fences).

Usage:
    python .claude/skills/sync-rsdc/scripts/reformat_tw.py docs/GeminiChatOrganizer-RSDC-tw.md
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Tuple

INLINE_TOKENS = [
    "child_process.spawn",
    "data/0-raw/", "data/1-sessions/", "data/2-turns_md/",
    "data/3-topics/", "data/4-exports/",
    "sync_config.yaml", "export_template.yaml",
    "parser.py", "topic_mgr.py", "render_md.py", "exporter.py",
    "visibilityFlag", "timestampUtc", "sessionIds",
    "sessionId", "topicId", "turnId", "beginTime", "endTime",
    "rawDir", "sessionsDir", "turnsMdDir", "topicsDir",
    "exportsDir", "sessionGapSeconds",
    "pathlib", "jinja2",
    "0-raw/",
]

BODY_ESCAPES = [
    (r"\\-", "-"),
    (r"\\_", "_"),
    (r"\\#", "#"),
    (r"\\\[", "["),
    (r"\\\]", "]"),
    (r"\\>", ">"),
    (r"\\\*", "*"),
    (r"\\=", "="),
    (r"\\\+", "+"),
]


def strip_hard_break(line: str) -> str:
    return re.sub(r"  +$", "", line)


def deescape_body(line: str) -> str:
    for pat, lit in BODY_ESCAPES:
        line = re.sub(pat, lit, line)
    return line


def convert_bullet(line: str) -> str:
    return re.sub(r"^(\s*)\*(\s)", r"\1-\2", line)


def shift_header(line: str, *, is_title: bool) -> str:
    m = re.match(r"^(#+)\s+(.*)$", line)
    if not m:
        return line
    hashes, text = m.group(1), m.group(2).strip()
    text = re.sub(r"^\*\*(.*)\*\*$", r"\1", text).strip()
    text = re.sub(r"(\d)\\\.", r"\1.", text)
    text = text.replace(r"\-", "-").replace(r"\_", "_")
    new_level = len(hashes) if is_title else min(len(hashes) + 1, 6)
    return ("#" * new_level) + " " + text


def looks_like_yaml(line: str) -> bool:
    # `key: value` where key is identifier-like.
    return bool(re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*:\s*\S", line))


def looks_like_tree_start(line: str) -> bool:
    return bool(re.match(r"^[A-Za-z0-9_-]+/\s*$", line.strip()))


def looks_like_tree_continuation(line: str) -> bool:
    return bool(re.match(r"^[├└│]", line)) or bool(re.match(r"^[ \t]+[├└│]", line))


def is_already_fenced(out: List[str]) -> bool:
    """True if the most recent fence is open (odd count)."""
    n = sum(1 for l in out if l.startswith("```"))
    return n % 2 == 1


def inline_code_tokens(line: str) -> str:
    if "`" in line:
        # Heuristic: leave lines with existing backticks alone (already partly coded).
        return line
    for tok in INLINE_TOKENS:
        # Word-boundary-ish: not preceded/followed by alphanum/underscore/dot/slash.
        pat = re.compile(
            r"(?<![A-Za-z0-9_./])" + re.escape(tok) + r"(?![A-Za-z0-9_./])"
        )
        line = pat.sub("`" + tok + "`", line)
    return line


def consume_block_until_blank(lines: List[str], i: int) -> Tuple[List[str], int]:
    block: List[str] = []
    while i < len(lines) and lines[i].strip():
        block.append(strip_hard_break(deescape_body(lines[i])))
        i += 1
    return block, i


def is_raw_paste(text: str) -> bool:
    """Heuristic: did this text come straight from a Word/Docs export?

    True if any of the unmistakable raw-paste artifacts are present:
        - bolded headers          `# **...**`
        - escaped numbered prefix `# 1\. Foo`
        - line-leading `*` bullets
        - escaped dashes in headers `### **Data \- topic**`
    """
    if re.search(r"^#+\s+\*\*", text, re.M):
        return True
    if re.search(r"^#+.*\\\.", text, re.M):
        return True
    if re.search(r"^\s*\*\s", text, re.M):
        return True
    if re.search(r"^#+.*\\-", text, re.M):
        return True
    return False


def next_nonblank(lines: List[str], start: int) -> int:
    j = start
    while j < len(lines) and not lines[j].strip():
        j += 1
    return j


def reformat(text: str) -> str:
    raw = is_raw_paste(text)
    raw_lines = text.splitlines()
    lines = [strip_hard_break(l) for l in raw_lines]

    # Idempotent-only mode: only inline-code missed identifiers in body text;
    # leave structure, headers, and fenced code alone.
    if not raw:
        out: List[str] = []
        in_fence = False
        for line in lines:
            if line.startswith("```"):
                in_fence = not in_fence
                out.append(line)
                continue
            if in_fence or line.startswith("#"):
                out.append(line)
                continue
            out.append(inline_code_tokens(line))
        return "\n".join(out).rstrip() + "\n"

    out: List[str] = []
    i = 0
    title_emitted = False
    last_header_was_yaml_config = False

    while i < len(lines):
        line = lines[i]

        # Headers
        if line.startswith("#"):
            new_line = shift_header(line, is_title=not title_emitted)
            title_emitted = True
            last_header_was_yaml_config = bool(
                re.match(r"^#+ Config - .+\.yaml\b", new_line)
            )
            out.append(new_line)
            i += 1
            continue

        # Already-fenced lines: pass through unchanged
        if line.startswith("```"):
            out.append(line)
            i += 1
            # Pass through until closing fence
            while i < len(lines) and not lines[i].startswith("```"):
                out.append(lines[i])
                i += 1
            if i < len(lines):
                out.append(lines[i])
                i += 1
            continue

        # **Syntax** marker → fence the next non-blank block as plain code
        if line.strip() == "**Syntax**":
            out.append(line)
            i += 1
            j = next_nonblank(lines, i)
            if j < len(lines) and lines[j].startswith("```"):
                # Already fenced — let the main loop pass through.
                continue
            while i < len(lines) and not lines[i].strip():
                out.append(lines[i])
                i += 1
            block, i = consume_block_until_blank(lines, i)
            if block:
                out.append("```")
                out.extend(block)
                out.append("```")
            continue

        # **Example** marker → fence as ```json
        if line.strip() == "**Example**":
            out.append(line)
            i += 1
            j = next_nonblank(lines, i)
            if j < len(lines) and lines[j].startswith("```"):
                continue
            while i < len(lines) and not lines[i].strip():
                out.append(lines[i])
                i += 1
            block, i = consume_block_until_blank(lines, i)
            if block:
                out.append("```json")
                out.extend(block)
                out.append("```")
            continue

        # Directory tree: line is `data/` (or similar dir/) followed by `├──`/`└──`
        if (
            looks_like_tree_start(line)
            and i + 1 < len(lines)
            and looks_like_tree_continuation(lines[i + 1])
        ):
            block = [strip_hard_break(deescape_body(line))]
            i += 1
            while i < len(lines) and lines[i].strip() and looks_like_tree_continuation(lines[i]):
                block.append(strip_hard_break(deescape_body(lines[i])))
                i += 1
            out.append("```")
            out.extend(block)
            out.append("```")
            continue

        # YAML config block: contiguous `key: value` lines, only after a Config heading
        if last_header_was_yaml_config and looks_like_yaml(line):
            block = []
            while i < len(lines) and looks_like_yaml(lines[i]):
                block.append(strip_hard_break(deescape_body(lines[i])))
                i += 1
            out.append("```yaml")
            out.extend(block)
            out.append("```")
            last_header_was_yaml_config = False
            continue

        # Normal body line
        line = convert_bullet(line)
        line = deescape_body(line)
        line = inline_code_tokens(line)
        out.append(line)
        i += 1

    # Single trailing newline
    return "\n".join(out).rstrip() + "\n"


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <path/to/RSDC-tw.md>", file=sys.stderr)
        return 2
    p = Path(argv[1])
    if not p.exists():
        print(f"error: {p} not found", file=sys.stderr)
        return 1
    src = p.read_text(encoding="utf-8")
    new = reformat(src)
    p.write_text(new, encoding="utf-8")
    print(f"reformatted {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
