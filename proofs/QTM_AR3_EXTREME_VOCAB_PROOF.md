# QTM-AR3 extreme vocabulary proof

Target is the same strict future `README.md` used by the QTD3/QTM-AR2 proof:

- base: `9832a2d424b8500bfcc01e088f6119f1419a09bb`
- target: `79915e036d80f98be9e72aa6dbd6b37a8d135f45`
- source: **2787 B**
- SHA-256: `4ce8d5577aad836ea1efb8a23358784a1aba7bdd98e9fb5b60de9833722b66aa`
- literal region after QTD COPY graph: **943 B**

The phrase vocabulary is reconstructed only from older model entries; no phrase dictionary bytes are sent in warm/shared mode.

`M=2^20, K=1`, minimum phrase length 2:

| vocabulary profile | byte core | core ratio | phrase events | literal bytes covered | timestamps | uint64 bytes | physical total |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 512 | 344 B | 8.101744x | 146 | 458 / 943 | 57 | 456 B | 800 B |
| 4096 | 253 B | 11.015810x | 168 | 687 / 943 | 82 | 656 B | 909 B |
| 8192 | 187 B | 14.903743x | 190 | 804 / 943 | 100 | 800 B | 987 B |
| 16384 | **161 B** | **17.310559x** | 214 | **842 / 943 = 89.29%** | 114 | 912 B | 1073 B |

Every row was decoded back to the exact 2787-byte target and passed SHA-256.

Important interpretation:

- `161 B` is the **ordinary byte-core size when the timestamp stream is an external second channel**.
- It is not standalone 17.31x compression. If timestamps are materialized as uint64, the 16K profile costs `161 + 114*8 = 1073 B` total.
- Byte-only QAU2 remains smaller at 461 B than any materialized AR3 temporal profile in this experiment.

The extreme result therefore demonstrates real learned byte-combination transfer into temporal state, not information disappearance.
