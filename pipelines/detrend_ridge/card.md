# Detrend · SNV · Ridge

A **fast linear** regression baseline.

## What it does

1. **Detrend** — removes low-order polynomial baseline curvature.
2. **SNV** — removes multiplicative scatter.
3. **Standardisation** of features and target.
4. **Ridge regression** (L2, `alpha=1.0`) — a well-conditioned high-dimensional linear
   fit, 5-split shuffle CV.

## When to use it

A quick sanity check and a surprisingly strong baseline on near-linear targets. Trains
in a blink; tune `alpha` by cross-validation for the best bias/variance trade-off.
