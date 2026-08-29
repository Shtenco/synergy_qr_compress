# SHTENCO All Archivers Extended Benchmark — 2026-08-29

## Scope

- Legacy exact baseline: **76 unique systems** (69 frozen + active Tier-1 rerun), corpus **11 × 32,768 B**, old current rows **154/154 PASS**.
- New same-corpus systems: **QTC1** and **QTC2 standalone**; both use the identical deterministic corpus and exact round-trip gate.
- Shared-model systems **QTD2/QTD3** are reported in a separate strict temporal track because an external reused model changes the accounting problem.
- Direct standard-codec rows are sanity baselines, not inserted into the production SHTENCO ranking.

## Extended production TOP-10 by geometric-mean compression ratio

| Rank | Engine | Geomean ratio | Run |
|---:|---|---:|---|
| 1 | SHTENCO OMNIA TIER1 V2 MAX | **30.335995×** | legacy-current |
| 2 | SHTENCO QTC1 TEMPORAL CONTAINER | **27.573204×** | new-20260829 |
| 3 | SHTENCO OMNIA TIER1 V2 BALANCED | **27.235040×** | legacy-current |
| 4 | SHTENCO GABRIEL-HORN TIER1 MAX | **24.759551×** | legacy-current |
| 5 | SHTENCO QTC2 STANDALONE | **24.486182×** | new-20260829 |
| 6 | SHTENCO GABRIEL-HORN TIER1 BALANCED | **24.459013×** | legacy-current |
| 7 | SHTENCO GRAAL-IGC TIER1 MAX | **22.633934×** | legacy-current |
| 8 | SHTENCO TSC-X TIER1 SPATIAL | **22.114639×** | legacy-current |
| 9 | SHTENCO SABF-X ULTIMATE GRAPH-AI | **21.920991×** | legacy-frozen |
| 10 | SHTENCO TSC-X TURBOSPATIAL GRAPH-AI | **21.907299×** | legacy-frozen |

## New same-corpus exact rows

| Engine | Geomean ratio | Geomean encode ms | Geomean decode ms | Geomean score | 11 datasets |
|---|---:|---:|---:|---:|:---:|
| QTC1 | **27.573204×** | 134.707 | 0.1035 | 0.204691 | PASS |
| QTC2-standalone | **24.486182×** | 134.289 | 0.1019 | 0.182339 | PASS |

Sanity baselines on the same bytes:

| Codec | Geomean ratio |
|---|---:|
| Brotli-11 | 24.316416× |
| Zstd-19 | 20.819189× |
| LZMA Extreme | 18.568363× |
| zlib-9 | 14.168369× |
| BZ2-9 | 14.103588× |
| rANS-O0 | 1.902948× |
| RAW | 1.000000× |

The local runtime did not have the Python `zstandard` package, so direct Zstd-19 was verified through the installed `zstd` CLI. A separate check tested both identity and delta8 Zstd-19 payloads; neither beat the QTC-selected payload on any of the 11 datasets, so the reported QTC1/QTC2 ratios are unchanged by that runtime limitation.

## Strict shared-temporal track — real future Git blobs

Targets: `README.md`, new `compression_lab/test_tier1_v2.py`, and new `.github/workflows/unified_tier1_v2_benchmark.yml`; total **10,011 B**. The full target SHA-256 is absent from training for every row.

| System | Containers | Ratio | Transport reduction | Weighted prior-model coverage |
|---|---:|---:|---:|---:|
| Direct Brotli-11 | 3,195 B | 3.133333× | 68.085106% | — |
| QTD2 | 2,807 B | **3.566441×** | **71.960843%** | 18.649486% |
| QTD3 | **2,392 B** | **4.185201×** | **76.106283%** | **40.055938%** |

QTD3 is **14.784467% smaller than QTD2** on this strict future-blob set, and **25.133020% smaller than direct Brotli-11**.

### QTD2 rows

| Target | Source | QTD2 | Coverage | Best profile |
|---|---:|---:|---:|---|
| README evolution | 2787 B | **672 B** | 61.930391% | 48/96/192 |
| new Tier-1 v2 test | 1111 B | **577 B** | 0.000000% | 24/48/96 |
| new unified workflow | 6113 B | **1558 B** | 2.306560% | 16/32/64 |

### QTD3 rows

| Target | Source | QTD3 | Brotli-11 | Coverage |
|---|---:|---:|---:|---:|
| README evolution | 2787 B | **589 B** | 1282 B | 66.164334% |
| new Tier-1 v2 test | 1111 B | **421 B** | 461 B | 81.638164% |
| new unified workflow | 6113 B | **1382 B** | 1452 B | 20.595452% |

## Accounting rule

QTD2/QTD3 transport sizes do **not** pretend that the shared model costs zero. The model is an external reusable asset, so transport and cold-start/model bytes are reported separately. A single-use cold start can expand data; the temporal advantage is meaningful when the model is reused across later objects.

## Methodology notes

1. The old 76-system baseline is preserved rather than reinterpreted. Its archived result used the same deterministic 11×32,768-byte corpus and exact byte equality + SHA-256 gate.
2. QTC1/QTC2 were rerun on those exact corpus generators. QTC1 has a 60-byte container header; QTC2 has a 108-byte header.
3. QTC routing tested identity/delta8 with raw, zlib-9, BZ2-9, LZMA Extreme, Brotli-11 and exact rANS-O0. Zstd-19 was checked separately as described above.
4. QTD2 was rerun with FastCDC profile search and exact chunk-reference reconstruction. The README row exactly reproduces the earlier 672-byte QTD2 proof.
5. QTD3 values come from the current strict Q4B1 walk-forward engine and its anti-leakage proof.
6. Timing from the 2026-07-30 frozen run is not mixed with new timing; only archive-size ratios are merged across runs.

## Conclusions

- **OMNIA V2 MAX remains the same-corpus byte leader.**
- **QTC1 becomes #2 overall by same-corpus geometric-mean ratio.**
- **QTC2 standalone enters at approximately #5** among the production leaders.
- **QTD3 is the current shared-temporal leader**, improving both transmitted bytes and prior-model coverage over QTD2.
- **SABF-X Tier1 Speed remains the latency/score class leader**; QTC1 is a ratio-first portfolio and its encode search is much slower.
