<!-- SPDX-License-Identifier: CeCILL-2.1 OR AGPL-3.0-or-later -->
# Python API reference

## Top-level

```{eval-rst}
.. automodule:: nirs4all_repository
   :members: get, fetch, list, card
   :undoc-members:
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
