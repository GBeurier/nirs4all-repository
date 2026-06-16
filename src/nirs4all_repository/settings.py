# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Runtime settings resolved from the environment.

Settings are intentionally tiny and read-only. Heavy paths (``root`` detection, cache
location) are resolved lazily so importing the package stays cheap.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

#: Default public base URL serving the catalogue and bundles.
DEFAULT_BASE_URL = "https://repository.nirs4all.org"


def _default_cache_dir() -> Path:
    """Return the OS cache directory for downloaded bundles."""
    env = os.environ.get("NIRS4ALL_REPOSITORY_CACHE")
    if env:
        return Path(env).expanduser()
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base).expanduser() if base else Path.home() / ".cache"
    return root / "nirs4all-repository"


def _env_root() -> Path | None:
    env = os.environ.get("NIRS4ALL_REPOSITORY_ROOT")
    return Path(env).expanduser() if env else None


def _extra_allowlist() -> tuple[str, ...]:
    raw = os.environ.get("NIRS4ALL_REPOSITORY_ALLOWLIST", "")
    return tuple(token.strip() for token in raw.split(",") if token.strip())


@dataclass(frozen=True)
class Settings:
    """Resolved runtime configuration.

    Attributes:
        root: explicit catalogue checkout root, or ``None`` to auto-detect.
        cache_dir: directory holding verified downloaded bundles.
        base_url: base URL for remote resolution.
        extra_allowlist: extra allowed module roots for the security scan. This is a
            *local developer convenience only* and is never consulted by the publication
            gate or CI (see :mod:`nirs4all_repository.security`).
    """

    root: Path | None = field(default_factory=_env_root)
    cache_dir: Path = field(default_factory=_default_cache_dir)
    base_url: str = field(default_factory=lambda: os.environ.get("NIRS4ALL_REPOSITORY_BASE_URL", DEFAULT_BASE_URL))
    extra_allowlist: tuple[str, ...] = field(default_factory=_extra_allowlist)


def get_settings() -> Settings:
    """Return freshly resolved :class:`Settings` from the current environment."""
    return Settings()
