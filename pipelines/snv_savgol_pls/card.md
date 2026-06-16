# SNV · Savitzky–Golay · PLS

A robust, general-purpose **regression baseline** for near-infrared spectra.

## What it does

1. **Standard Normal Variate (SNV)** — removes multiplicative scatter and offset.
2. **Savitzky–Golay (1st derivative)** — `window_length=11`, `polyorder=2`; sharpens
   absorption bands and removes slow baseline drift.
3. **Min–max scaling** of features and target.
4. **PLS regression** with 12 latent components, selected by a 5-split shuffle CV.

## When to use it

Reach for this first when modelling a continuous constituent (protein, moisture, sugar,
…) from raw NIRS reflectance. It is fast, well-conditioned, and rarely overfits.

## Notes

Tune `n_components` to your dataset; 8–15 is typical. Swap the first-derivative SG for a
second-derivative filter when broad overlapping bands dominate.
