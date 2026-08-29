# QTM-AR2 real README proof

Target: `README.md` at `79915e036d80f98be9e72aa6dbd6b37a8d135f45`  
Base: `9832a2d424b8500bfcc01e088f6119f1419a09bb`

Exact measured results on the same real future README used by the QTD3/QTD4.1 proof:

- source: **2787 B**
- QTD3: **589 B**
- QTD4.1: **571 B**
- QTM-AR1: **468 B**
- QTM-AR2 separate streams: **465 B**
- QTM-AR2 Unified / `QAU2`: **461 B**
- QAU2 ratio: **6.045553×**
- target SHA-256: `4ce8d5577aad836ea1efb8a23358784a1aba7bdd98e9fb5b60de9833722b66aa`
- byte equality: **PASS**
- SHA-256 equality: **PASS**

QAU2 learns and arithmetic-codes both the temporal COPY graph and literal byte probabilities. Skeleton and literal symbols share one arithmetic coder state, so the second stream termination and stream-boundary metadata disappear.

## Conservative existing 3-target lower bound

No unmeasured improvement is assumed for the other two existing real-Git targets. Keeping their exact QTD3 containers as fallback:

`461 + 421 + 1382 = 2264 B`

Therefore the already-proven non-regressing warm lower bound is:

`10011 -> 2264 B = 4.421820×`

This is **5.351% smaller than QTD3 aggregate** and **29.139% smaller than direct Brotli-11 aggregate** on the same three-target set.

Cold historical-model bytes are not declared free.

## Temporal combination carrier

QAU2 can be represented bijectively through Unix-ns timestamps using two simultaneous channels:

1. centered low-20-bit jitter states (approximately ±0.524288 ms), and
2. a combinadic rank from selecting `K` timestamp positions among `M` candidate slots.

For the 461-byte QAU2 blob, examples include:

- `M=256, K=32`: **161 timestamps**, ~24.219 bits/timestamp, ~1.346 s span;
- `M=16384, K=12`: **121 timestamps**, ~31.583 bits/timestamp, ~171.808 s span;
- `M=65536, K=8`: **113 timestamps**, **34.0 bits/timestamp**, ~962.086 s span.

All temporal profiles were decoded back to the exact QAU2 bytes. Timestamp carrier capacity is reported separately from byte compression; materialized uint64 timestamp cost is not treated as free.