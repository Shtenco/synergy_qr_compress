# Fusion V5-X2 milestones

## Promoted exact X2 results

### 1. FORMAT-EXACT — real PDF

`gold_statement.pdf`:

- source 459,506 B
- legacy V4-compatible floor 395,027 B
- V5 123,518 B
- archive-size improvement **3.198x** vs V4
- standalone exact SHA-256 PASS

### 2. Segment-MDL — heterogeneous fixed MEGA bundle

Eight 8-KiB fixed classes concatenated into one 65,536-B object:

- legacy V4-compatible floor 4,170 B
- V5 segment archive 1,982 B
- archive-size improvement **2.104x** vs V4
- standalone exact PASS

## Rejected / not promoted

QTD5 approximate dynamic-programming COPY parser: real README remained **571 B → 571 B** against QTD4.1. The experiment is documented but not part of the production router.

## Next targets

- exact PNG/DEFLATE decision-transcript route;
- variable-boundary Segment-DP instead of fixed block-size candidates;
- compact route/parameter entropy coding;
- learned lower-bound route predictor for >=2x encode-speed/score;
- AR4 variable grammar/trie temporal model.
