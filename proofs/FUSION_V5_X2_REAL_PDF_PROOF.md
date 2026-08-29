# Fusion V5-X2 — real PDF exact proof

Date: 2026-08-29

## Target

Real user file: `gold_statement.pdf`

- source bytes: **459,506**
- SHA-256: `cec6df2f85d70a16aa3d9f5752f0d1f74856a11be7d4704e776e71a1f06fc59f`

## Result

Local exact run of `qr_temporal/fusion_v5_x2.py`:

- valid legacy Fusion-V4-compatible floor: **395,027 B** = **1.163227x**
- Fusion V5-X2: **123,518 B** = **3.720154x**
- final size reduction versus legacy V4: **68.7318%**
- ratio multiplier versus legacy V4: **3.19813x**
- decode: byte equality PASS
- SHA-256 equality PASS

## Why this is lossless

The FORMAT-EXACT route scans candidate PDF `stream` payloads. A stream is replaced by its semantic uncompressed bytes only if, for some zlib level 1..9:

`zlib.compress(zlib.decompress(original_stream), level) == original_stream`

Only such byte-reproducible streams are normalized. The decoder recompresses those semantic streams with the recorded zlib level and concatenates untouched literal PDF bytes around them.

On this target the normalizer found **100 exact zlib-reproducible streams** and exposed **3,324,153 semantic bytes**. The normalized token stream was then globally entropy-compressed. No approximate PDF regeneration is used.

## Accounting

This is standalone byte-exact compression. No shared historical model, external timestamp carrier or free side channel is required for the 123,518-byte result.
