# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""The package __version__ must match the repository-root VERSION file."""

from __future__ import annotations

from pathlib import Path

import nirs4all_repository


def test_version_matches_version_file():
    version_file = Path(__file__).resolve().parent.parent / "VERSION"
    assert version_file.read_text().strip() == nirs4all_repository.__version__
