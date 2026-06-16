# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Tests for the safe Markdown renderer (no stored XSS)."""

from __future__ import annotations

from nirs4all_repository.markdown_safe import render_markdown


def test_escapes_raw_html():
    html = render_markdown("Hello <script>alert(1)</script>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_headings_and_paragraphs():
    html = render_markdown("# Title\n\nA paragraph.")
    assert "<h1>Title</h1>" in html
    assert "<p>A paragraph.</p>" in html


def test_lists():
    html = render_markdown("- one\n- two")
    assert "<ul>" in html and "<li>one</li>" in html


def test_inline_code_and_emphasis():
    html = render_markdown("Use `code` and **bold** and *italic*.")
    assert "<code>code</code>" in html
    assert "<strong>bold</strong>" in html
    assert "<em>italic</em>" in html


def test_safe_link():
    html = render_markdown("[site](https://nirs4all.org)")
    assert '<a href="https://nirs4all.org"' in html


def test_unsafe_link_scheme_dropped():
    html = render_markdown("[x](javascript:alert(1))")
    assert "javascript:" not in html
    assert "x" in html


def test_fenced_code_block_escaped():
    html = render_markdown("```\n<b>not bold</b>\n```")
    assert "<pre><code>" in html
    assert "&lt;b&gt;" in html
