# QTD2 blind Git-history proof — ai_compress README

This benchmark is deliberately **unseen-target**. The target full file is not present in the model and its SHA-256 is rejected if it appears in the training manifest.

## Git lineage

Training snapshots:

1. `69a1926fb7fbf9e2685e7cc42abdd1643a9545d7` — README blob `2b5c55172e7234a948bb0b9f89f18beb5e369169`, 1261 B.
2. `9832a2d424b8500bfcc01e088f6119f1419a09bb` — README blob `8dfc12344e6570da5103ebbe485b5fe60cede6ba`, 1837 B.

Unseen target:

- commit `79915e036d80f98be9e72aa6dbd6b37a8d135f45`;
- README Git blob `a0f96cb4e53b84d15963b165b514ce0e65986745`;
- 2787 B;
- SHA-256 `4ce8d5577aad836ea1efb8a23358784a1aba7bdd98e9fb5b60de9833722b66aa`;
- target SHA present in training: **false**.

The target commit adds the new `Точный корпусный benchmark` section, so a material part of the target genuinely did not exist in training.

## QTD2 architecture used

`previous Git snapshots -> FastCDC-style gear chunks -> deduplicated temporal chunk bank -> chunk-reference prediction -> literal residual -> lossless codec router -> temporal address + model_id + target SHA-256`

Residual candidates implemented: raw, zlib-9, bz2-9, LZMA extreme, Brotli-11 over the reference stream, rANS order-0, trained Zstd dictionary when `zstandard` is installed, and optional Gabriel Horn MAX when the sibling `ai_compress` module is importable.

Python `brotli` in the test runtime does not expose RFC 9841 Shared Brotli dictionary APIs, so this run must **not** be labeled an RFC-9841 Shared Brotli result. Brotli is applied after shared chunk references have removed predictable bytes.

## Best transport result

Best FastCDC profile: `48/96/192` bytes (min/avg/max).

| Metric | Result |
|---|---:|
| Target size | 2787 B |
| Training-model serialized size | 2892 B |
| Unique temporal chunks | 18 |
| Target bytes supplied by shared model | 1726 B |
| Honest model coverage | 61.930391101543% |
| Genuinely literal/unseen bytes before entropy coding | 1061 B |
| Chunk references | 14 |
| Raw reference/residual token stream | 1092 B |
| Winning residual codec | `brotli-11-refstream` |
| Compressed payload | 568 B |
| Complete QTD2 blind container | 672 B |
| Source -> QTD2 transport reduction | 75.888051668461% |
| Exact byte round-trip | PASS |
| SHA-256 round-trip | PASS |
| Target full SHA absent from training | PASS |

Direct lossless baselines on the same target in this runtime:

| Codec | Bytes |
|---|---:|
| brotli11 | 1282 |
| bz2_9 | 1398 |
| lzma_extreme | 1496 |
| raw | 2787 |
| zlib9 | 1501 |

QTD2's 672-byte complete transport container is **47.581903276131% smaller than the 1282-byte direct Brotli-11 archive** on this exact target.

## Coverage frontier

A smaller FastCDC profile can maximize reuse instead of minimizing transport bytes. With profile `4/8/16`, the same unseen target reaches about **66.7384284% exact chunk coverage**, but the larger reference stream makes the final container larger. QTD2 therefore treats coverage and final transport size as separate objectives.

## Cold-start accounting

For the first target only, model + container = 3564 B, which is an expansion of 27.879440258342% versus the 2787-byte target. The shared model is therefore not free.

Against raw storage, the model cost amortizes after **2 target objects of this size/behavior**. Against direct Brotli-11, the same one-time model cost amortizes after **5 comparable target objects**. This is why QTD2 reports both transport size and model size rather than hiding the dictionary.

## Reproduce

Run `benchmark_qtd2_git_history.py` with local files checked out from the exact Git commits and their expected Git blob SHA-1 values. The benchmark aborts on any blob mismatch or target leakage.
