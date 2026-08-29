# Fusion V4 ML + big benchmark status — 2026-08-29

## Temporal ML

Added `qr_temporal/qtm_ar.py`.

QTM-AR keeps the exact QTD4.1 COPY graph and replaces hard literal prediction with a timestamp-weighted probabilistic model + exact arithmetic coding. `pack_max` is non-regressing: it returns the smaller QTD4.1 or QTM-AR child.

Real future README result:

- source: 2787 B
- QTD3: 589 B
- QTD4.1: 571 B
- **QTM-AR: 468 B = 5.955128×**
- byte equality + SHA-256: PASS

Conservative warm 3-target lower bound with QTD3 fallback on the two unrerun targets:

- source: 10011 B
- transport: 2271 B
- ratio: **4.408190×**
- 5.0585% smaller than QTD3
- 28.9202% smaller than direct Brotli-11

No cold-model improvement is claimed.

## 12-case temporal walk-forward suite

Six temporal families × two future targets, 8192 B each, each target trained only on four older timestamped versions:

- Brotli-11: 11.267923×
- QTM-AR-MAX: **9.908524×**
- QTD4.1-EXT: 9.895049×
- QTM-AR raw route: 7.858613×

This is intentionally retained as a mixed/negative result: ML does not universally beat a strong standalone codec. The MDL MAX route prevents regression versus QTD4.1.

## MEGA-31 standalone corpus

31 exact objects, 996855 source bytes total. It includes 8/32/64-KiB structured objects and real PNG/PDF/JPG/code slices.

Our ratio leaders:

1. Fusion V4 Native MAX — **20.857785×**
2. Fusion V3 MAX — 19.962969×
3. Fusion V3 FAST — 18.594996×
4. OMNIA V2 Balanced — 14.810679×
5. QTC4-MDL — 12.145344×
6. OMNIA V2 Speed — 10.996296×
7. Q20-PACKED — 9.858758×
8. Gabriel Tier1 Speed — 7.581920×

Our ratio/encode-ms score leaders:

1. Fusion V3 FAST — **1.424417**
2. OMNIA V2 Speed — 0.644359
3. Q20-PACKED — 0.404552
4. Fusion V3 MAX — 0.249263
5. QTC4-MDL — 0.210021
6. OMNIA V2 Balanced — 0.097076
7. Fusion V4 Native MAX — 0.085295
8. Gabriel Tier1 Speed — 0.019913

Foreign ratio leaders on the same MEGA-31 set:

1. Brotli-11 — **13.427815×**
2. Zstd-22 — 12.038291×
3. XZ/LZMA2-9e — 10.804751×
4. Zopfli-zlib — 9.468225×
5. zlib-9 — 8.778113×
6. gzip-9 — 8.617776×
7. bzip2-9 — 8.362717×
8. LZ4-HC16 — 6.743703×

## Timing caveat

The local environment did not expose the Python `zstandard` package. Historical Tier-1 can be made runnable through a CLI compatibility shim, but exhaustive OMNIA/Gabriel profiles then spend most of their time spawning CLI processes. For that reason the local MEGA speed table uses Fusion V4 **Native MAX** and keeps historical OMNIA/Gabriel MAX ratios in the original reproducible 85-system table rather than presenting wrapper overhead as algorithmic speed.
