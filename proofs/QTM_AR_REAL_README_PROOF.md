# QTM-AR real Git temporal proof — 2026-08-29

QTM-AR is the probabilistic ML layer on top of the Fusion V4.1 / QTD4.1 COPY graph. It learns byte probability distributions only from strictly older timestamped history and arithmetic-codes literal bytes directly from those distributions.

## Real target

- repository: `Shtenco/ai_compress`
- path: `README.md`
- historical/base commit: `9832a2d424b8500bfcc01e088f6119f1419a09bb`
- future/target commit: `79915e036d80f98be9e72aa6dbd6b37a8d135f45`
- source bytes: **2787 B**
- target SHA-256: `4ce8d5577aad836ea1efb8a23358784a1aba7bdd98e9fb5b60de9833722b66aa`

The target bytes/SHA are not part of the historical model. The model timestamp is strictly earlier than the target timestamp; both QTD4.1 and QTM-AR reject temporal/model mismatches.

## Exact results

| Engine | Container | Ratio |
|---|---:|---:|
| Stored QTD3 proof | 589 B | 4.7317× |
| QTD4.1 | 571 B | 4.880911× |
| **QTM-AR** | **468 B** | **5.955128×** |

For QTM-AR:

- QTD4.1 COPY coverage retained: **1844 / 2787 B = 66.164334%**
- literal bytes modeled: **943 B**
- COPY skeleton: **14 B** compressed
- arithmetic-coded literal stream: **387 B**
- compact header/varints: **67 B**
- byte equality after decode: **PASS**
- SHA-256 equality: **PASS**

Reductions:

- QTM-AR vs QTD4.1: **18.04% smaller**
- QTM-AR vs stored QTD3 container: **20.54% smaller**

## Conservative 3-target warm lower bound

The previous measured QTD3 walk-forward aggregate is `10011 → 2392 B`. Without assuming any QTM gain on its other two targets, use QTM-AR only for README and keep exact QTD3 fallback for the remaining targets:

`468 + 421 + 1382 = 2271 B`

Therefore the already demonstrated non-regressing warm hybrid is:

`10011 → 2271 B = 4.408190×`

This is **5.0585% smaller than QTD3** and **28.9202% smaller than direct Brotli-11 (3195 B)** on those same target sizes.

This is a warm/shared transport result. No cold-start improvement is claimed by this proof; reusable model bytes must be accounted separately.

## Model

The learned probability model combines:

- timestamp-decayed global byte priors;
- order-1…6 historical context distributions;
- stronger prior for the same path;
- same-position prior from the newest historical version;
- online adaptation on bytes already reconstructed from the target;
- COPY bytes as free online adaptation observations.

Literal bytes are not reduced to one hard prediction. The full 256-way distribution drives an exact arithmetic coder, so partial predictive information contributes to compression.
