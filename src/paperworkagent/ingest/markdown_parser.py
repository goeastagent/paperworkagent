from __future__ import annotations

import re

from markdown_it import MarkdownIt

from paperworkagent.models import Manuscript, Section


def parse_markdown(text: str) -> Manuscript:
    """Parse a Markdown manuscript into sections with line-number provenance."""
    md = MarkdownIt()
    tokens = md.parse(text)
    lines = text.splitlines()

    sections: list[Section] = []
    current_title = ""
    current_level = 0
    current_start = 0
    current_paragraphs: list[str] = []

    for token in tokens:
        if token.type == "heading_open":
            level = int(token.tag[1])  # h1 -> 1, h2 -> 2, ...
            line = token.map[0] if token.map else 0
            if current_title or current_paragraphs:
                sections.append(
                    Section(
                        title=current_title,
                        level=current_level,
                        content="\n".join(current_paragraphs),
                        start_line=current_start,
                        end_line=line - 1 if line > 0 else current_start,
                        paragraphs=current_paragraphs[:],
                    )
                )
            current_title = ""
            current_level = level
            current_start = line
            current_paragraphs = []

        elif token.type == "inline" and not current_title and current_level > 0:
            current_title = token.content.strip()

        elif token.type == "inline" and token.content.strip():
            current_paragraphs.append(token.content.strip())

    if current_title or current_paragraphs:
        sections.append(
            Section(
                title=current_title,
                level=current_level,
                content="\n".join(current_paragraphs),
                start_line=current_start,
                end_line=len(lines) - 1,
                paragraphs=current_paragraphs[:],
            )
        )

    return Manuscript(sections=sections, raw_text=text)


_SECTION_ALIASES: dict[str, str] = {
    "introduction": "introduction",
    "background": "introduction",
    "methods": "methods",
    "materials and methods": "methods",
    "methodology": "methods",
    "results": "results",
    "findings": "results",
    "discussion": "discussion",
    "conclusion": "discussion",
    "conclusions": "discussion",
    "limitations": "discussion",
    "abstract": "abstract",
}


def normalize_section_name(title: str) -> str:
    """Map a section heading to a canonical section name."""
    key = re.sub(r"[\d.]+\s*", "", title).strip().lower()
    return _SECTION_ALIASES.get(key, key)
