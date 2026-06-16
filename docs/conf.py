# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Sphinx configuration for the nirs4all-repository documentation."""

from __future__ import annotations

import re
from pathlib import Path

# -- Project information -----------------------------------------------------

project = "nirs4all-repository"
author = "Gregory Beurier"
copyright = "2026, Gregory Beurier — CIRAD"  # noqa: A001

_init = (Path(__file__).resolve().parent.parent / "src" / "nirs4all_repository" / "_version.py").read_text(encoding="utf-8")
_match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', _init)
release = _match.group(1) if _match else "0.0.0"
version = release

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "myst_parser",
    "sphinx_copybutton",
    "sphinx_design",
    "sphinxext.opengraph",
]

myst_enable_extensions = ["colon_fence", "deflist", "fieldlist"]
myst_heading_anchors = 3

source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
root_doc = "index"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

napoleon_google_docstring = True
napoleon_numpy_docstring = False
autodoc_typehints = "description"
autodoc_member_order = "bysource"
autodoc_mock_imports = ["nirs4all", "nirs4all_datasets", "dag_ml", "numpy"]

intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}

# -- HTML output -------------------------------------------------------------

html_theme = "furo"
html_title = f"nirs4all-repository {release}"
html_logo = "../assets/brand/horizontal.svg"
html_favicon = "../assets/brand/favicon.ico"
html_theme_options = {
    "sidebar_hide_name": True,
    "light_css_variables": {"color-brand-primary": "#AC564A", "color-brand-content": "#8f463c"},
    "dark_css_variables": {"color-brand-primary": "#c4715f", "color-brand-content": "#c4715f"},
}

ogp_site_url = "https://nirs4all-repository.readthedocs.io/en/latest/"
ogp_image = "https://repository.nirs4all.org/assets/brand/og.png"
