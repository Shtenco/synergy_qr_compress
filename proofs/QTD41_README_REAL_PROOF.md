# QTD4.1 real README proof — 2026-08-29

Target is the real future Git blob `README.md` at `79915e036d80f98be9e72aa6dbd6b37a8d135f45`.

- target bytes: **2787 B**
- target Git blob: `a0f96cb4e53b84d15963b165b514ce0e65986745`
- target SHA-256: `4ce8d5577aad836ea1efb8a23358784a1aba7bdd98e9fb5b60de9833722b66aa`
- historical source used by the local V4.1 micro-proof: `README.md` at base commit `9832a2d424b8500bfcc01e088f6119f1419a09bb`
- historical base bytes: **1837 B**
- QTD4.1 COPY coverage: **1844 / 2787 = 66.164334%**
- QTD4.1 literal bytes: **943 B**
- QTD4.1 skeleton: **14 B**
- QTD4.1 literal residual after MDL: **489 B**
- compact header + varints: **68 B**
- full QTD4.1 warm container: **571 B**
- QTD4.1 warm ratio: **4.880911×**
- decode byte equality: **PASS**
- decode SHA-256: **PASS**

Stored QTD3 proof for the same target used a richer two-entry model but obtained the same 66.164334% COPY coverage and a **589 B** warm container. QTD4.1 is therefore **18 B / 3.055?% smaller** on this target while preserving the same reconstructed-byte coverage. Exact calculated reduction is `100*(1-571/589) = 3.055?%` (rounding in reports should be generated programmatically).

The selected literal predictor on this large newly inserted README section was `raw`; historical n-gram prediction was tested but MDL correctly rejected it. This is an important negative result: V4.1 does not force context prediction when it increases description length.

The full three-case side-by-side benchmark is implemented in `benchmark_qtd41_walkforward.py`; it builds the same historical QTD3 model, adapts the identical entries/model fingerprint to QTD4.1, and reports warm plus cold accounting separately.
