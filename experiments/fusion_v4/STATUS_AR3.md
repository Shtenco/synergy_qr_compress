# Fusion V4 AR3 status

Branch: `fusion-v4-ar3`

Implemented:

- deterministic temporal phrase vocabulary, lengths **2,3,4,5,6,8,12,16 bytes**;
- timestamp/recency weighting and same-path weighting;
- byte-only phrase expert `QAP3`;
- non-regressing byte MAX router (`QTD4.1 / QTM-AR1 / QAU2 / QAP3`);
- temporal phrase mode `QXU3` where exact target Unix-ns is `timestamp[0]`;
- temporal channel carries path-id, segment count and learned phrase event metadata;
- phrase event arithmetic stream is mapped to combinadic timestamp choices plus 20-bit centered ns residual states;
- exact temporal cutoff, target-leakage guard and full SHA-256 validation.

## Real README

Byte-only:

`2787 -> QAU2 461 B = 6.045553x`

`QAP3 = 471 B`, therefore phrase mode correctly loses to QAU2 in byte-only MAX.

External temporal carrier, aggressive 2-byte+ vocabulary:

`2787 -> 344 B byte core = 8.101744x`

with `146 phrase events`, `458 / 943 literal bytes` explained by historical byte combinations, and `56 timestamps` at `M=2^20,K=1`.

If those timestamps are stored as uint64, total is `344 + 56*8 = 792 B`; this is not claimed as standalone compression.

## 12-case strict temporal Pareto

Exact repository implementation, 12 walk-forward cases:

| Mode | Geomean byte-core ratio | Aggregate core | Geomean materialized ratio | Aggregate timestamps | Phrase bytes covered |
|---|---:|---:|---:|---:|---:|
| QXU3-L2 | **11.016612x** | 10670 B | 4.005144x | 4368 | 31304 B |
| QXU3-L6 | 7.090785x | 19851 B | 5.807651x | 436 | 7832 B |
| QXU3-L12 | 6.861451x | 20696 B | 6.161511x | 101 | 2540 B |
| QAU2 byte-only | 6.631850x | 20950 B | **6.631850x** | 0 | 0 |

Conclusion: learned byte combinations materially improve the **external byte-core frontier**, while QAU2 remains the best physical byte-only representation on this suite. This split is intentional and must remain visible in all reports.
