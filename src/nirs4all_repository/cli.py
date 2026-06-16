# SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later
"""The ``n4a-repository`` command-line interface.

The CLI subcommands are the build/maintenance interface for the catalogue (there is no
Makefile): list/show/get for consumers; add/validate/scan/build/site/evaluate/publish
for maintainers.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from ._version import __version__
from .settings import DEFAULT_BASE_URL

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="The nirs4all pipeline repository: store, validate, secure and serve pipelines.",
)


def _resolved_root(root: Path | None) -> Path:
    from .store import detect_root

    detected = detect_root(root)
    if detected is None:
        typer.secho("error: not inside a nirs4all-repository checkout (no pipelines/ + catalog/)", fg="red", err=True)
        raise typer.Exit(2)
    return detected


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


@app.command("list")
def list_cmd(
    framework: str = typer.Option(None, help="Filter by framework (nirs4all | dag-ml)."),
    task: str = typer.Option(None, help="Filter by task."),
    tag: str = typer.Option(None, help="Filter by tag."),
    kind: str = typer.Option(None, help="Filter by kind (recipe | fitted)."),
    trust: str = typer.Option(None, help="Filter by trust tier."),
) -> None:
    """List catalogue pipelines."""
    import nirs4all_repository as n4r

    entries = n4r.list(framework=framework, task=task, tag=tag, kind=kind, trust=trust)
    if not entries:
        typer.echo("(no pipelines)")
        return
    for entry in entries:
        typer.echo(f"{entry['id']:<28} {entry['framework']:<8} {entry['kind']:<7} {entry['trust']:<12} {entry['summary']}")


@app.command()
def show(name: str) -> None:
    """Show a pipeline's full descriptor (JSON)."""
    import nirs4all_repository as n4r

    typer.echo(json.dumps(n4r.card(name), indent=2, ensure_ascii=False))


@app.command()
def get(
    name: str,
    with_artifacts: bool = typer.Option(False, "--with-artifacts", help="Also download fitted artifact blobs."),
) -> None:
    """Resolve a pipeline and print the local bundle path."""
    import nirs4all_repository as n4r

    path = n4r.fetch(name, with_artifacts=with_artifacts)
    typer.echo(str(path))


@app.command()
def scan(
    name: str,
    root: Path = typer.Option(None, help="Catalogue root (default: auto-detect)."),
) -> None:
    """Run the security scan on a pipeline's recipe."""
    from .recipes import load_recipe_file
    from .security import scan_config
    from .store import load_descriptor, pipeline_dir

    base = _resolved_root(root)
    descriptor = load_descriptor(base, name)
    recipe = load_recipe_file(pipeline_dir(base, name) / descriptor.recipe.path)
    result = scan_config(recipe, descriptor.recipe.format)
    if result.ok:
        typer.secho(f"{name}: security scan clean", fg="green")
    else:
        for finding in result.findings:
            typer.secho(f"{name}: {finding}", fg="red", err=True)
        raise typer.Exit(1)


@app.command()
def validate(
    name: str = typer.Argument(None, help="Pipeline id (default: validate all)."),
    all_: bool = typer.Option(False, "--all", help="Validate every pipeline."),
    strict: bool = typer.Option(False, "--strict", help="Also run framework-level recipe checks."),
    root: Path = typer.Option(None, help="Catalogue root (default: auto-detect)."),
) -> None:
    """Statically validate one or all pipelines (schema, structure, checksums, security)."""
    from .validate import validate_all, validate_pipeline

    base = _resolved_root(root)
    reports = validate_all(base, strict=strict) if (all_ or name is None) else [validate_pipeline(base, name, strict=strict)]

    failed = 0
    for report in reports:
        if report.ok:
            extra = "" if not report.publication_blockers else f"  [not publishable: {len(report.publication_blockers)}]"
            typer.secho(f"OK   {report.pipeline_id}{extra}", fg="green")
        else:
            failed += 1
            typer.secho(f"FAIL {report.pipeline_id}", fg="red")
            for message in (*report.errors, *report.security_findings):
                typer.secho(f"       {message}", fg="red", err=True)
    if failed:
        typer.secho(f"{failed} pipeline(s) failed validation", fg="red", err=True)
        raise typer.Exit(1)
    typer.secho(f"all {len(reports)} pipeline(s) valid", fg="green")


@app.command()
def build(
    base_url: str = typer.Option(DEFAULT_BASE_URL, help="Base URL embedded in the index."),
    root: Path = typer.Option(None, help="Catalogue root (default: auto-detect)."),
) -> None:
    """Regenerate per-bundle manifests and catalog/index.json."""
    from .builder import build_catalog

    base = _resolved_root(root)
    ids = build_catalog(base, base_url=base_url)
    typer.secho(f"built {len(ids)} pipeline(s) + catalog/index.json", fg="green")


@app.command()
def site(
    out: Path = typer.Option(Path("site"), help="Output directory for the static site."),
    base_url: str = typer.Option(DEFAULT_BASE_URL, help="Canonical site base URL."),
    root: Path = typer.Option(None, help="Catalogue root (default: auto-detect)."),
) -> None:
    """Render the static catalogue website."""
    from .site import build_site

    base = _resolved_root(root)
    target = build_site(base, out, base_url=base_url)
    typer.secho(f"site written to {target}", fg="green")


@app.command()
def add(
    name: str,
    recipe: Path = typer.Option(..., "--recipe", help="Path to the recipe JSON/YAML file."),
    framework: str = typer.Option("nirs4all", help="nirs4all | dag-ml."),
    summary: str = typer.Option("", help="One-line summary."),
    root: Path = typer.Option(None, help="Catalogue root (default: auto-detect)."),
) -> None:
    """Scaffold a new pipeline bundle from a recipe file."""
    from .scaffold import scaffold_pipeline

    base = _resolved_root(root)
    created = scaffold_pipeline(base, name, recipe, framework=framework, summary=summary)
    typer.secho(f"created {created}", fg="green")


@app.command()
def evaluate(
    name: str,
    root: Path = typer.Option(None, help="Catalogue root (default: auto-detect)."),
) -> None:
    """Run a pipeline against its reference dataset and compare to expected metrics."""
    import nirs4all_repository as n4r

    from .evaluate import evaluate_pipeline

    base = _resolved_root(root)
    pipeline = n4r.get(name, root=base)
    outcome = evaluate_pipeline(pipeline)
    for line in outcome.comparisons:
        typer.echo(f"  {line}")
    color = "green" if outcome.status.value == "validated" else "red"
    typer.secho(f"{name}: {outcome.status.value} — {outcome.message}", fg=color)
    if outcome.status.value != "validated":
        raise typer.Exit(1)


@app.command()
def publish(
    name: str,
    root: Path = typer.Option(None, help="Catalogue root (default: auto-detect)."),
) -> None:
    """Report whether a pipeline is ready to be published (publication gate)."""
    from .store import load_descriptor

    base = _resolved_root(root)
    descriptor = load_descriptor(base, name)
    blockers = descriptor.publication_blockers()
    if not blockers:
        typer.secho(f"{name}: ready to publish", fg="green")
        return
    for blocker in blockers:
        typer.secho(f"{name}: BLOCKER — {blocker}", fg="yellow", err=True)
    raise typer.Exit(1)


def main() -> None:
    """Entry point used by the ``n4a-repository`` console script."""
    app()


if __name__ == "__main__":  # pragma: no cover
    app()
