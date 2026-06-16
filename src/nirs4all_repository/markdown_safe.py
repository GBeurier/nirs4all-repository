# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""A deliberately minimal, safe Markdown→HTML renderer for authored cards.

Authored content (``card.md``) is untrusted: it may be submitted by a contributor and
is rendered into a public static site. To avoid stored XSS we **escape everything**
first and then re-introduce only a fixed, safe subset of formatting. Raw HTML in the
source is escaped, never passed through. Link targets are restricted to
``http:``/``https:``/``mailto:``.

This is intentionally not a full CommonMark implementation; it covers headings,
paragraphs, lists, fenced/inline code, emphasis, and safe links — enough for a card.
"""

from __future__ import annotations

import html
import re

_SAFE_HREF = re.compile(r"^(https?:|mailto:)", re.IGNORECASE)
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_CODE = re.compile(r"`([^`]+)`")


def _inline(text: str) -> str:
    """Render inline formatting on an already-HTML-escaped *text*."""
    # Inline code first (its content must not be further formatted).
    placeholders: list[str] = []

    def _stash_code(match: re.Match[str]) -> str:
        placeholders.append(f"<code>{match.group(1)}</code>")
        return f"\x00{len(placeholders) - 1}\x00"

    text = _CODE.sub(_stash_code, text)

    def _link(match: re.Match[str]) -> str:
        label, href = match.group(1), match.group(2)
        # href was HTML-escaped already; compare on the unescaped scheme.
        raw_href = html.unescape(href)
        if not _SAFE_HREF.match(raw_href):
            return label
        return f'<a href="{href}" rel="nofollow noopener">{label}</a>'

    text = _LINK.sub(_link, text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _ITALIC.sub(r"<em>\1</em>", text)

    for index, value in enumerate(placeholders):
        text = text.replace(f"\x00{index}\x00", value)
    return text


def render_markdown(source: str) -> str:
    """Render *source* Markdown to a safe HTML fragment."""
    lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)
    list_type: str | None = None

    def close_list() -> None:
        nonlocal list_type
        if list_type is not None:
            out.append(f"</{list_type}>")
            list_type = None

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Fenced code block
        if stripped.startswith("```"):
            close_list()
            i += 1
            code: list[str] = []
            while i < n and not lines[i].strip().startswith("```"):
                code.append(html.escape(lines[i]))
                i += 1
            i += 1  # skip closing fence
            out.append("<pre><code>" + "\n".join(code) + "</code></pre>")
            continue

        if not stripped:
            close_list()
            i += 1
            continue

        # Headings
        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            close_list()
            level = len(heading.group(1))
            content = _inline(html.escape(heading.group(2).strip()))
            out.append(f"<h{level}>{content}</h{level}>")
            i += 1
            continue

        # Unordered list
        if re.match(r"^[-*+]\s+", stripped):
            if list_type != "ul":
                close_list()
                out.append("<ul>")
                list_type = "ul"
            item = _inline(html.escape(re.sub(r"^[-*+]\s+", "", stripped)))
            out.append(f"<li>{item}</li>")
            i += 1
            continue

        # Ordered list
        if re.match(r"^\d+\.\s+", stripped):
            if list_type != "ol":
                close_list()
                out.append("<ol>")
                list_type = "ol"
            item = _inline(html.escape(re.sub(r"^\d+\.\s+", "", stripped)))
            out.append(f"<li>{item}</li>")
            i += 1
            continue

        # Paragraph (collect consecutive non-blank, non-special lines)
        close_list()
        para: list[str] = []
        while i < n and lines[i].strip() and not re.match(r"^(#{1,6}\s|```|[-*+]\s|\d+\.\s)", lines[i].strip()):
            para.append(html.escape(lines[i].strip()))
            i += 1
        out.append("<p>" + _inline(" ".join(para)) + "</p>")

    close_list()
    return "\n".join(out)
