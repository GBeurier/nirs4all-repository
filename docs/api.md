<!-- SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later -->
# Python API reference

## Top-level

```{eval-rst}
.. automodule:: nirs4all_repository
   :members: list, card, get, fetch
   :undoc-members:
```

### Provider-facing entry points

Explicit ``*_pipeline`` names for `nirs4all-core` / `nirs4all-ui` /
`nirs4all-providers` clients that want a provider-style contract.
`get_pipeline_list()`, `get_pipeline()`, and `get_bundle()` are the canonical
provider-facing entry points. They keep the **same read-only catalogue
semantics and signatures** as the catalogue-native `list()`, `get()`, and
`fetch()` APIs, and are frozen as part of the 0.1.0 public API.

```{eval-rst}
.. autofunction:: nirs4all_repository.get_pipeline_list
.. autofunction:: nirs4all_repository.get_pipeline
.. autofunction:: nirs4all_repository.get_bundle
```

## Pipeline

```{eval-rst}
.. autoclass:: nirs4all_repository.bridge.Pipeline
   :members:
```

## Descriptor schema

`Pipeline.recipe()` returns the exact parsed JSON tree (dict or list), after
structural checks. Both step aliases together are refused. `to_nirs4all()` allows
only root `pipeline`/`steps`, `random_state`, `name`, `description`; other root keys
raise `BridgeError` rather than risk silent loss. Neither bridge qualifies execution.

`Pipeline.execution_requirements()` derives framework/format from the validated
descriptor and class-reference module roots from the recipe, with versions,
profiles, operations, artifact versions and dependency coverage explicitly unknown. It works without
a manifest, including downloaded bundles. The same block is included in list/index
entries and manifests. `card()` continues returning the unchanged v1 descriptor;
requirements are derived metadata rather than a descriptor field. See
{doc}`SPECIFICATION` §6 for the versioned contract and qualification limits.

Dependency observations inspect explicit serialized components and format-specific
step/operator contexts. Dotted metadata and ordinary parameter strings are not
imports. `python_dependencies` remains unknown even for an empty root list.
Index readers reject malformed or future requirements; missing old blocks remain
unqualified. Recipe JSON preserves recursive mapping order; site parity also checks
types, order and complete variant mappings.

```{eval-rst}
.. automodule:: nirs4all_repository.schema
   :members: PipelineDescriptor, Recipe, Artifact, Reference, Evaluation, Provenance, Governance
   :undoc-members:
```

## Settings

```{eval-rst}
.. autoclass:: nirs4all_repository.settings.Settings
   :members:

.. autofunction:: nirs4all_repository.settings.get_settings
```

## Validation & security

```{eval-rst}
.. autofunction:: nirs4all_repository.validate.validate_pipeline
.. autofunction:: nirs4all_repository.validate.validate_all
.. autofunction:: nirs4all_repository.security.scan_config
.. autofunction:: nirs4all_repository.security.scan_pickle_bytes
```

## Building the catalogue

```{eval-rst}
.. autofunction:: nirs4all_repository.builder.build_catalog
.. autofunction:: nirs4all_repository.site.build_site
```

## V1 release-train surface contract

`contracts/public-v1-surface.n4a.json` freezes the Repository exports, provider
entry points, bundled nirs4all recipe set, and the exact R1/R2/R3 Python source
identities. `scripts/check_public_v1_surface.py` validates those three source
checkouts in isolated interpreter processes and emits one JSON receipt suitable
for the product release lock. `--surface-only` is available for a local package
check, but does not prove release-train compatibility.

## Optional local project client

The independent, opt-in `ProjectClient` and POSIX ASGI service are documented in
[Local project service](PROJECT_SERVICE.md). They do not extend `__all__` or alter
public catalogue name resolution.
