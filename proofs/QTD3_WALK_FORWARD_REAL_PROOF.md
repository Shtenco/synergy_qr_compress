# QTD3 strict blind walk-forward proof — 2026-08-29

QTD3 is tested only on **future real Git blobs** from `Shtenco/ai_compress`. A target is rejected if its full SHA-256 already exists in training, and the model's newest timestamp must be strictly earlier than the target timestamp.

## Aggregate

- Real future targets: **3**
- Source bytes: **10,011 B**
- Full QTD3 `Q4B1` containers: **2,392 B**
- Direct Brotli-11 total: **3,195 B**
- Physical transport reduction vs raw: **76.106283089%**
- QTD3 reduction vs direct Brotli-11: **25.133020344%**
- Weighted bytes reconstructed from prior model: **40.055938468%**
- Byte equality: **PASS**
- SHA-256 equality: **PASS**
- Target SHA absent from training: **PASS**

## Rows

| Target | Git blob | Source | QTD3 | Brotli-11 | Model coverage | QTD3 vs Brotli |
|---|---|---:|---:|---:|---:|---:|
| `README.md` | `a0f96cb4e53b…` | 2787 B | 589 B | 1282 B | 66.1643% | 54.0562% |
| `compression_lab/test_tier1_v2.py` | `54254728b8a1…` | 1111 B | 421 B | 461 B | 81.6382% | 8.6768% |
| `.github/workflows/unified_tier1_v2_benchmark.yml` | `6b8b678d5bf7…` | 6113 B | 1382 B | 1452 B | 20.5955% | 4.8209% |

## Predictor selected

All three rows selected `temporal-external-lz`: long COPY ranges are searched across older repository blobs; unmatched bytes remain literal and the resulting reference stream is routed through verified lossless codecs. In these runs Brotli-11 won the residual MDL competition.

## Integrity / anti-leakage

- full target SHA-256 is not in the training model;
- training `max_unix_ns < target_unix_ns`;
- model fingerprint is carried by the container;
- final output length and SHA-256 are verified;
- wrong model / corrupted container are rejected by unit tests.

## Reproduce repository-wide

`benchmark_qtd3_walkforward.py` uses `git ls-tree`, `git log` and `git show` on a local clone to build a text/code model from historical repository state and then evaluate strictly later target blobs. The stored proof is conservative: it uses explicitly materialized historical blobs whose Git hashes were checked against GitHub.

The shared model is not counted as zero-cost data. Model serialized bytes and cold total are retained in the JSON report; QTD3 transport savings apply when the model is already shared/reused.
