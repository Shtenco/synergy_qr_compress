# Fusion V4 / QTM-AR2 status — 2026-08-29

Implemented on branch `fusion-v4-ar2`:

- timestamp-weighted literal probability model inherited from QTM-AR1;
- learned temporal COPY-graph model for `OP / entry delta / offset delta / copy length delta / literal length delta`;
- O(n) historical skeleton-prior learner using only older revisions;
- `QAU2` unified arithmetic state for COPY graph + literal symbols;
- exact temporal combination carrier: combinadic slot selection + centered 20-bit jitter;
- anti-leakage model fingerprint, temporal cutoff and target SHA-256 checks;
- exact unit tests and real-Git walk-forward benchmark harness.

## Real measured frontier

Same future README target:

`QTD3 589 -> QTD4.1 571 -> QTM-AR1 468 -> QTM-AR2 465 -> QAU2 461 B`

`2787 -> 461 B = 6.045553x`.

Conservative three-target real-Git lower bound using QAU2 only where measured and exact QTD3 fallback elsewhere:

`10011 -> 2264 B = 4.421820x`.

## 12-case strict synthetic walk-forward suite

- Brotli-11: `11.267923x`
- QTM-AR2-MAX: `9.909460x`
- QTD4.1-EXT: `9.895049x`
- QTM-AR1: `7.858613x`
- QTM-AR2 Unified without fallback: `6.631850x`

MAX selections: QTD4.1 `10/12`, QTM-AR1 `1/12`, QTM-AR2 Unified `1/12`.

This negative result is retained: learned COPY-graph arithmetic coding is not universally smaller on heterogeneous temporal streams, therefore the production route remains MDL/non-regressing.

## Timestamp carrier

For the 461-byte QAU2 blob:

- low-latency `M=256,K=32`: 161 timestamps, ~1.346 s;
- balanced `M=16384,K=12`: 121 timestamps, ~171.808 s;
- dense `M=65536,K=8`: 113 timestamps, 34.0 bits/timestamp, ~962.086 s;
- max-density tested `M=1048576,K=8`: 105 timestamps, 38.0 bits/timestamp, ~14293.664 s.

If timestamps are stored as uint64 values, their materialized byte cost is counted separately. No information-theory exception is claimed.