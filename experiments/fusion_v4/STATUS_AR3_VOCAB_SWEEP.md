# QTM-AR3 variable-vocabulary sweep

Branch: `fusion-v4-ar3`

Strict 12-case walk-forward suite, 8192 bytes per target, exact byte equality + SHA-256.
Temporal profile uses `M=2^20, K=1`, minimum phrase length 2. Phrase vocabulary is rebuilt from older timestamped model state only.

| Mode | Geomean byte-core ratio | Aggregate core | Geomean materialized ratio | Aggregate materialized | Timestamps | Phrase events | Phrase bytes covered |
|---|---:|---:|---:|---:|---:|---:|---:|
| QXU3-V16384 | **16.187560x** | **7814 B** | 3.395973x | 49566 B | 5219 | 10588 | **36644 B** |
| QXU3-V8192 | 15.970938x | 7980 B | 3.382109x | 49764 B | 5223 | 10926 | 36388 B |
| QXU3-V4096 | 15.871760x | 8025 B | 3.388249x | 49777 B | 5219 | 11059 | 36295 B |
| QXU3-V512 | 11.016612x | 10670 B | 3.995256x | 45654 B | 4373 | 10395 | 31304 B |
| QAU2 byte-only | 6.631850x | 20950 B | **6.631850x** | **20950 B** | 0 | 0 | 0 B |

Interpretation:

- The learned byte-combination vocabulary systematically moves the **external temporal byte-core frontier**: aggregate ordinary core bytes drop from `20950` to `7814`.
- The missing information is not discarded; it lives in `5219` Unix-ns timestamps for the 16K profile.
- When timestamps are materialized as ordinary uint64 values, the total is larger than QAU2. Therefore QAU2 remains the physical byte-only winner on this suite.
- QTM-AR3 must expose both metrics: `core ratio` and `materialized total ratio`.

Real README extreme profile remains:

`2787 -> 161 B core = 17.310559x`, with 842 / 943 literal bytes explained by historical byte combinations. The 114 timestamps make materialized total 1073 B, so this is not a standalone 17.31x claim.
