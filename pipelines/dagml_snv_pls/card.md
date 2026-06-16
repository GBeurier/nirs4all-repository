# dag-ml — SNV · Savitzky–Golay · PLS

The robust SNV/SG/PLS regression baseline, expressed as a **dag-ml pipeline DSL**.

## Why it exists

The repository serves both the `nirs4all` and `dag-ml` ecosystems through one storage
envelope. This recipe is the dag-ml counterpart of
[`snv_savgol_pls`](snv_savgol_pls.html): the same preprocessing and PLS model, but
authored as a dag-ml DSL that a dag-ml-aware runtime compiles into a graph + campaign
template.

## What it does

1. **SNV** scatter correction.
2. **Savitzky–Golay** first derivative (`window_length=11`, `polyorder=2`).
3. **Min–max scaling**.
4. **Shuffle split** (5 × 25 %) and a **12-component PLS** model.

Provenance, content-addressing, and the cross-language contract are identical to the
nirs4all recipes — only the recipe grammar differs.
