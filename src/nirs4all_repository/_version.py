# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Single source of truth for the package version.

Kept byte-identical to the repository-root ``VERSION`` file (which the shared
``version-guard`` workflow and ``nirs4all-cockpit`` read); a unit test enforces the
match.
"""

__version__ = "0.1.0"
