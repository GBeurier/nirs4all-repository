# MSC · PLS

The **classic** near-infrared regression pipeline.

## What it does

1. **Multiplicative Scatter Correction (MSC)** — regresses each spectrum onto the mean
   spectrum to remove scatter from particle size and path-length differences.
2. **Standardisation** of features and target.
3. **PLS regression** with 10 latent components, 5-fold KFold cross-validation.

## When to use it

The default first choice for powdered or granular samples where scatter dominates. MSC
and SNV are close cousins — try both; MSC is preferred when a stable reference spectrum
is meaningful for your sample set.
