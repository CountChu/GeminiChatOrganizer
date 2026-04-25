from __future__ import annotations

import re

from bs4 import BeautifulSoup
from markdownify import markdownify as _md


def html_to_markdown(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    cleaned = str(soup)
    md = _md(cleaned, heading_style="ATX", bullets="-", strip=["meta", "link"])
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return md
