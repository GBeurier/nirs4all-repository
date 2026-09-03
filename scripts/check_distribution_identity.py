#!/usr/bin/env python3
# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Verify that release distributions and the optional release tag match VERSION."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from pathlib import Path


def identity_errors(names: Sequence[str], *, version: str, release_tag: str | None = None) -> list[str]:
    """Return errors for distribution names or a release tag that do not match *version*."""
    expected = {
        f"nirs4all_repository-{version}-py3-none-any.whl",
        f"nirs4all_repository-{version}.tar.gz",
    }
    actual = set(names)
    errors: list[str] = []
    if actual != expected:
        errors.append(f"distribution identity mismatch: expected {sorted(expected)}, found {sorted(actual)}")
    if release_tag and release_tag != f"v{version}":
        errors.append(f"release tag {release_tag!r} does not match VERSION {version!r}")
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"))
    parser.add_argument("--version-file", type=Path, default=Path("VERSION"))
    parser.add_argument("--release-tag", default=os.environ.get("RELEASE_TAG") or None)
    args = parser.parse_args(argv)

    version = args.version_file.read_text(encoding="utf-8").strip()
    names = sorted(path.name for path in args.dist_dir.iterdir() if path.is_file())
    errors = identity_errors(names, version=version, release_tag=args.release_tag)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"distribution identity OK: v{version} ({', '.join(names)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
