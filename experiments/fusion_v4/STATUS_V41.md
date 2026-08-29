# Fusion V4.1 status

Branch: `fusion-v4-1`

Implemented:

- compact QTD4.1 `Q41C` container;
- COPY-graph delta coding for `(entry, offset, length)`;
- external-LZ and same-path lineage route search;
- literal predictors: raw, previous-model continuation, next-model backfill, bridge, left-byte, historical ngram4;
- independent skeleton and literal-residual entropy selection;
- model fingerprint, temporal cutoff, target leakage guard, full target SHA-256;
- exact unit tests;
- side-by-side QTD3/QTD4.1 real-Git walk-forward benchmark harness with warm and cold accounting.

Measured now:

- real future `README.md`: QTD3 stored proof `589 B`; QTD4.1 `571 B`; same COPY coverage `66.164334%`; **3.056027% smaller**, exact SHA-256 PASS;
- QTD3 cross-file unit fixture: comparable absolute-token baseline `98 B`; QTD4.1 `87 B`; **11.22449% smaller**, exact PASS;
- QTD3 lineage/context fixture: QTD4.1 selected historical `ngram4` for the all-literal route; literal residual compressed to `44 B`; exact PASS.

Negative result retained:

- on the real README's 943-byte newly inserted section, ngram4 did not beat raw literal coding; MDL selected raw. Context prediction is optional and is never forced when it expands the description.

CI note:

The repository's existing matrix CI currently ends in platform-level failure before job steps are exposed (`steps: []`) on this branch as well as the parent experiment branch. Local `py_compile` plus exact round-trip gates pass. The full 3-case benchmark harness is committed and ready to run against a local/authenticated clone of `Shtenco/ai_compress`.
