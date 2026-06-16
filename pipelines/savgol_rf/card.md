# Savitzky–Golay (2nd derivative) · Random Forest

A **non-linear** regression pipeline for when PLS underfits.

## What it does

1. **Savitzky–Golay, 2nd derivative** — `window_length=15`, `polyorder=2`; resolves
   overlapping absorption bands and removes baseline curvature.
2. **SNV** — removes residual multiplicative scatter.
3. **Random forest** — 400 trees, depth 12, evaluated with a 5-split shuffle.

## When to use it

Try this when the target responds non-linearly to the spectrum, or when you want
out-of-the-box feature-importance diagnostics. Expect higher variance than PLS; keep an
eye on the validation/test gap.
