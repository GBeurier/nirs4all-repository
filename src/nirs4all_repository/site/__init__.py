# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Static catalogue-site renderer for ``repository.nirs4all.org``."""

from __future__ import annotations

from .build import build_site, render_detail, render_index

__all__ = ["build_site", "render_index", "render_detail"]
