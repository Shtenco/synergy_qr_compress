# Fusion V5-X2 — Segment-MDL X2 proof

Date: 2026-08-29

## Fixed heterogeneous bundle

The test concatenates eight fixed 8192-byte MEGA corpus classes, without tuning their content after seeing the result:

1. `source_code_8k`
2. `structured_binary_8k`
3. `repeated_text_8k`
4. `image_like_8k`
5. `sparse_weights_8k`
6. `version_snapshots_8k`
7. `json_graph_logs_8k`
8. `bip39_text_8k`

Total source: **65,536 B**.

## Exact result

- valid legacy Fusion-V4-compatible floor: **4,170 B** = **15.716x**
- Fusion V5-X2 Segment-MDL: **1,982 B** = **33.0656x**
- archive-size multiplier: **4,170 / 1,982 = 2.104x**
- byte reduction versus V4: **52.47%**
- selected V5 mode: compact segment container
- exact decode: PASS
- SHA-256 equality: PASS

## Why the gain exists

The bundle is heterogeneous. A whole-file V4 route must choose one global transform family. V5 splits the object into bounded segments and lets each segment select its own reversible expert (raw, Brotli, Zstd, zlib, delta, shuffle+delta, second-order delta, gradient). The outer object carries a single SHA-256 rather than one digest per segment.

The segment search is bounded: cheap zlib-1 structural probes shortlist only the two most promising expensive transform candidates before Brotli-11 is evaluated.

## Interpretation

This is a standalone exact compression result; no shared historical model or external timestamp carrier is required. It validates the audit prediction that segment-level MDL can produce >2x improvement over whole-file routing on heterogeneous data.
