#!/usr/bin/env python3
# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""Fail when a GitHub Release is missing package distribution assets."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import Any

API_ROOT = "https://api.github.com"


def release_url(repo: str, tag: str | None) -> str:
    """Return the GitHub REST URL for a latest or tagged release."""
    if repo.count("/") != 1:
        raise ValueError(f"expected repository as OWNER/REPO, got {repo!r}")
    if tag:
        quoted = urllib.parse.quote(tag, safe="")
        return f"{API_ROOT}/repos/{repo}/releases/tags/{quoted}"
    return f"{API_ROOT}/repos/{repo}/releases/latest"


def fetch_release(repo: str, tag: str | None, token: str | None) -> dict[str, Any]:
    """Fetch release metadata from the GitHub REST API."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "nirs4all-repository-release-assets-check",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(release_url(repo, tag), headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub release query failed ({exc.code}): {body}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("GitHub release query returned a non-object payload")
    return payload


def asset_names(release: dict[str, Any]) -> list[str]:
    """Extract release asset names from GitHub release metadata."""
    assets = release.get("assets", [])
    if not isinstance(assets, list):
        raise RuntimeError("GitHub release payload has a non-list assets field")
    names: list[str] = []
    for asset in assets:
        if isinstance(asset, dict) and isinstance(asset.get("name"), str):
            names.append(asset["name"])
    return names


def asset_errors(names: Sequence[str], *, min_assets: int, require_python_dist: bool) -> list[str]:
    """Return human-readable asset validation errors."""
    errors: list[str] = []
    if len(names) < min_assets:
        errors.append(f"expected at least {min_assets} release asset(s), found {len(names)}")
    if require_python_dist:
        if not any(name.endswith(".whl") for name in names):
            errors.append("missing wheel asset (*.whl)")
        if not any(name.endswith(".tar.gz") for name in names):
            errors.append("missing sdist asset (*.tar.gz)")
    return errors


def github_token() -> str | None:
    """Return a GitHub token from the environment or the local gh CLI."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    try:
        result = subprocess.run(["gh", "auth", "token"], check=True, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        pass
    else:
        token = result.stdout.strip()
        if token:
            return token
    return gh_hosts_token()


def gh_hosts_token() -> str | None:
    """Return a token from the local gh hosts file when the CLI cannot print it."""
    config_dir = os.environ.get("GH_CONFIG_DIR")
    hosts_path = (Path(config_dir) if config_dir else Path.home() / ".config" / "gh") / "hosts.yml"
    if not hosts_path.is_file():
        return None
    try:
        import yaml

        data = yaml.safe_load(hosts_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    host_config = data.get("github.com") if isinstance(data, dict) else None
    token = host_config.get("oauth_token") if isinstance(host_config, dict) else None
    return token if isinstance(token, str) and token else None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"), help="GitHub repository as OWNER/REPO. Defaults to GITHUB_REPOSITORY.")
    parser.add_argument("--tag", default=None, help="Release tag to check. Defaults to the latest published release.")
    parser.add_argument("--min-assets", type=int, default=1, help="Minimum number of attached release assets.")
    parser.add_argument("--require-python-dist", action=argparse.BooleanOptionalAction, default=True, help="Require both a wheel (*.whl) and sdist (*.tar.gz) asset.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not args.repo:
        parser.error("--repo is required when GITHUB_REPOSITORY is not set")
    if args.min_assets < 0:
        parser.error("--min-assets must be non-negative")

    try:
        release = fetch_release(args.repo, args.tag, github_token())
        names = asset_names(release)
        errors = asset_errors(names, min_assets=args.min_assets, require_python_dist=args.require_python_dist)
    except Exception as exc:
        print(f"release asset check failed: {exc}", file=sys.stderr)
        return 2

    tag = release.get("tag_name") or args.tag or "latest"
    if errors:
        rendered_names = ", ".join(names) if names else "none"
        print(f"{args.repo}@{tag}: release has {len(names)} asset(s): {rendered_names}", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"{args.repo}@{tag}: release assets OK ({', '.join(names)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
