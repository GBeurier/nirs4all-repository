# Core Portable SNV + Savitzky-Golay + PLS

This recipe is the repository-side fixture for the V1 provider/repository/core
roundtrip gate. It deliberately uses only operators in the current
`nirs4all-core` portable subset:

- `KennardStoneSplitter`
- `StandardNormalVariate`
- `SavitzkyGolay`
- `PLSRegression`

The recipe is not a benchmark winner. Its job is to prove that the repository
can serve a static pipeline descriptor that thin provider clients can resolve
and core language bindings can load without importing the Python provider layer.
