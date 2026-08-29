# QTM-AR3 real README proof

Strict temporal target is the same future `README.md` used by QTD3/QTM-AR2:

- base: `9832a2d424b8500bfcc01e088f6119f1419a09bb`
- target: `79915e036d80f98be9e72aa6dbd6b37a8d135f45`
- source bytes: **2787 B**
- SHA-256: `4ce8d5577aad836ea1efb8a23358784a1aba7bdd98e9fb5b60de9833722b66aa`

Measured byte-only lineage:

- QTD3: **589 B**
- QTD4.1: **571 B**
- QTM-AR1: **468 B**
- QAU2: **461 B**
- QAP3 learned-phrase byte-only expert: **471 B**

Therefore AR3 phrase coding is **not** claimed as a new byte-only frontier on this target; MAX must retain QAU2.

## Temporal phrase carrier

QXU3 keeps full SHA-256 and model fingerprint in the byte core. Exact target Unix-ns, target path id, segment count, phrase-event count/gaps/ranks are carried by a strictly increasing Unix-ns timestamp stream. Phrase vocabulary is rebuilt deterministically from historical model entries only.

At `M=2^20, K=1`:

| minimum phrase | core bytes | core ratio | phrase events | covered literal bytes | timestamps | materialized total |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | **344 B** | **8.101744×** | 146 | 458 / 943 | 56 | 792 B |
| 3 | 369 B | 7.552846× | 90 | 361 / 943 | 37 | 665 B |
| 4 | 410 B | 6.797561× | 34 | 198 / 943 | 16 | 538 B |
| 5 | 421 B | 6.619952× | 24 | 161 / 943 | 12 | 517 B |
| 6 | 437 B | 6.377574× | 9 | 86 / 943 | 7 | 493 B |
| 8 | 444 B | 6.277027× | 4 | 56 / 943 | 5 | 484 B |
| 12 | 445 B | 6.262921× | 3 | 48 / 943 | 4 | **477 B** |

All rows were decoded back to the exact target and passed SHA-256.

Interpretation:

- **External temporal carrier:** the aggressive 2-byte+ mode reduces the ordinary byte core from QAU2 461 B to **344 B**, but the missing information resides in timestamps.
- **Materialized uint64 timestamps:** `344 + 56×8 = 792 B`, so it is not standalone compression.
- The light L12 mode has only four timestamp values and totals 477 B, still slightly above byte-only QAU2 461 B.

The temporal carrier is therefore reported as a second physical channel, never as free byte compression.
