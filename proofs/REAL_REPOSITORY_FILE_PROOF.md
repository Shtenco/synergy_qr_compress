# Real repository file proof — 2026-08-29

This proof deliberately separates **shared-model coverage** from **physical byte compression**.

## Real source file used for executable proof

Repository: `Shtenco/ai_compress`

Path: `compression_lab/umd_selector.py`

Git blob SHA-1: `570901580714dabc86e5f3b2305a8147bef2ef2b`

Size: `1553` bytes.

The benchmark reconstructs Git's blob hash from the local source bytes before running QTC2. This binds the test to the actual repository blob rather than to a synthetic substitute.

Observed source SHA-256:

`338ba6009f611789aea3cbe11f5cf10d876ccc1b2ef9816abca1dbd826fa71f2`

## QTC2 exact result

The real file was inserted into a one-entry QTD1 temporal model and encoded with QTC2 exact mode.

| Metric | Result |
|---|---:|
| Source | 1553 B |
| QTD1 model | 1622 B |
| QTC2 residual payload | 0 B |
| QTC2 container | 108 B |
| Shared-model coverage | 100% |
| Byte equality after decode | true |
| SHA-256 equality after decode | true |
| Transport reduction, source -> QTC2 container | 93.0457179652285898% |
| Theoretical reduction if only an 8-byte timestamp were transported | 99.4848679974243400% |
| Cold total, model + QTC2 | 1730 B |
| Cold reduction | -11.3972955569864778% (expansion) |

The zero residual proves that the timestamp-addressed shared model accounts for 100% of this file. It does **not** prove that 1553 bytes were physically compressed into zero bytes: the information is present in the external model.

The machine-readable result is in `proofs/real_ai_compress_umd_selector_2026-08-29.json`.

## Reproduce locally

Clone both repositories next to each other, install `qr_compress`, then run:

```bash
python benchmark_real_repo_file.py \
  ../ai_compress/compression_lab/umd_selector.py \
  --expected-git-sha 570901580714dabc86e5f3b2305a8147bef2ef2b \
  -o proofs/reproduced_umd_selector.json
```

The benchmark refuses to continue if the local file's Git blob SHA-1 differs.

## Why 99.9999999% physical compression cannot be demonstrated on this repository file

A reduction of `99.9999999%` leaves only `10^-9` of the source size in the encoded representation.

Therefore an encoded representation of `E` bytes requires a source of at least:

```text
N >= E * 1,000,000,000 bytes
```

So the exact lower bounds are:

| Encoded representation | Minimum source size for 99.9999999% reduction |
|---|---:|
| 1 byte | 1,000,000,000 B |
| 8-byte UNIX timestamp | 8,000,000,000 B |
| Current 108-byte QTC2 exact container | 108,000,000,000 B |

No byte-level encoding of a 1553-byte file can meet that target while emitting even one byte.

## Bound on the largest real Python file in `ai_compress/compression_lab`

`compression_lab/gabriel_horn_engine.py` is a real repository blob:

- Git blob SHA-1: `ac621bdbc28993eb4273bec55f143f4259f3632c`
- size: `26,395` bytes.

Even under an ideal exact shared-model match:

- current QTC2 exact container = 108 bytes -> reduction `99.59083159689335%`;
- hypothetical timestamp-only representation = 8 bytes -> reduction `99.9696912293995%`;
- even a one-byte code would only give about `99.9962114%`.

Thus `99.9999999%` physical byte compression is mathematically impossible for this real file under any non-empty byte representation.

## What *is* legitimately demonstrated

QTC2 can demonstrate **100% model coverage** on a real repository file with `0` residual bytes and exact SHA-256 round-trip. This means the file is fully recoverable from a shared model selected by the temporal address.

For a compression claim, however, the transport bytes and the cost/amortization of the shared model must be reported separately. `model_coverage_percent = 100` must not be renamed to `physical_compression_percent = 100`.
