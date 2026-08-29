# Fusion V5-X2 status

Date: 2026-08-29

## Implemented

- isolated branch `fusion-v5-x2` based on `fusion-v4-ar3`;
- legacy V4-compatible candidate is always part of the search;
- compact segment-MDL with one outer SHA-256 and no per-segment digest;
- cheap structural screening before expensive Brotli-11 transform evaluation;
- exact zlib-stream semantic normalization for PDF-like containers;
- conditional second-stage recompression only when complete bytes shrink;
- exact verification before candidate admission;
- pytest coverage for generic round-trip, non-regression, semantic zlib stream and sparse route.

## Measured selected-12 result

Representative MEGA cases: source code, JSON graph logs, structured binary, image-like, version snapshots, repeated text, sparse weights, BIP39 text, real PNG64, real PDF64, real JPG64, random8k.

- legacy V4-compatible geomean: **13.267479x**
- Fusion V5-X2 geomean: **14.457763x**
- relative ratio improvement: **+8.9714%**

The gain is deliberately non-uniform. Most already-won V4 cases return the legacy archive unchanged. The strongest new case is `real_pdf64`:

- V4: **52,501 B**, 1.248281x
- V5: **18,737 B**, 3.497678x
- byte reduction vs V4: **64.3112%**

## Full real PDF proof

`gold_statement.pdf`:

- 459,506 B source
- V4-compatible floor: 395,027 B
- V5: **123,518 B**
- ratio: **3.720154x**
- V5/V4 ratio multiplier: **3.19813x**
- SHA-256 exact PASS

## Next X2 modules

1. `FORMAT-EXACT-DEFLATE`: preflate-style correction transcript for non-zlib-identical DEFLATE, especially PNG IDAT.
2. `SEGMENT-DP`: variable segment boundaries rather than fixed block-size sweeps.
3. `ROUTE-ANS`: entropy-code route IDs, lengths and parameters.
4. `COPY-DP`: optimal QTD history parsing rather than greedy matches.
5. `AR4-GRAMMAR`: variable-length grammar trie + true code-length phrase DP + temporal combinadic carrier.
6. learned lower-bound router to shortlist candidates and attack the current encode-time cost.
