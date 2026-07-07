<!-- SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later -->
# Python API reference

## Top-level

```{eval-rst}
.. automodule:: nirs4all_repository
   :members: list, card, get, fetch
   :undoc-members:
```

### Provider-facing helpers

Explicit ``*_pipeline`` names for `nirs4all-core` / `nirs4all-ui` /
`nirs4all-providers` clients that want a provider-style contract. They are thin
helpers with the **same read-only catalogue semantics and signatures** as the
canonical functions above (`get_pipeline_list` -> :func:`list`, `get_pipeline` ->
:func:`get`, `get_bundle` -> :func:`fetch`), and are frozen as
part of the 0.1.0 public API.

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
