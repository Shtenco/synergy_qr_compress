from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal, ROUND_CEILING, getcontext
from pathlib import Path

from qr_temporal import TemporalSample, train_temporal_dictionary, pack_v2, unpack_v2, inspect_v2

getcontext().prec = 50
TARGET_PERCENT = Decimal("99.9999999")


def git_blob_sha1(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def reduction_percent_decimal(original_bytes: int, encoded_bytes: int) -> Decimal:
    if original_bytes == 0:
        return Decimal(100) if encoded_bytes == 0 else Decimal("-Infinity")
    return Decimal(100) * (Decimal(1) - Decimal(encoded_bytes) / Decimal(original_bytes))


def minimum_source_bytes_for_target(encoded_bytes: int, target_percent: Decimal = TARGET_PERCENT) -> int:
    if encoded_bytes <= 0:
        return 0
    remaining_fraction = Decimal(1) - target_percent / Decimal(100)
    required = Decimal(encoded_bytes) / remaining_fraction
    return int(required.to_integral_value(rounding=ROUND_CEILING))


def run(source: Path, unix_ns: int, expected_git_sha: str | None = None) -> dict:
    data = source.read_bytes()
    actual_git_sha = git_blob_sha1(data)
    if expected_git_sha is not None and actual_git_sha != expected_git_sha.lower():
        raise SystemExit(
            f"Git blob mismatch: expected {expected_git_sha.lower()}, got {actual_git_sha}"
        )

    model = train_temporal_dictionary([TemporalSample(unix_ns, data)])
    packed = pack_v2(data, model=model, unix_ns=unix_ns)
    restored = unpack_v2(packed.blob, model=model)
    meta = inspect_v2(packed.blob, model=model)

    if restored != data:
        raise AssertionError("byte equality failed")
    source_sha256 = hashlib.sha256(data).hexdigest()
    restored_sha256 = hashlib.sha256(restored).hexdigest()
    if restored_sha256 != source_sha256:
        raise AssertionError("SHA-256 equality failed")

    model_bytes = len(model.to_bytes())
    container_bytes = len(packed.blob)
    cold_total_bytes = model_bytes + container_bytes
    transport_reduction = reduction_percent_decimal(len(data), container_bytes)
    timestamp_reduction = reduction_percent_decimal(len(data), 8)
    cold_reduction = reduction_percent_decimal(len(data), cold_total_bytes)

    result = {
        "source": str(source),
        "source_bytes": len(data),
        "git_blob_sha1": actual_git_sha,
        "source_sha256": source_sha256,
        "mode": meta["mode"],
        "model_coverage_percent": meta["model_coverage_percent"],
        "payload_bytes": meta["payload_size"],
        "container_bytes": container_bytes,
        "qtd_model_bytes": model_bytes,
        "cold_total_bytes": cold_total_bytes,
        "byte_equal": restored == data,
        "sha256_equal": restored_sha256 == source_sha256,
        "transport_reduction_percent": str(transport_reduction),
        "timestamp_8byte_theoretical_reduction_percent": str(timestamp_reduction),
        "cold_reduction_percent": str(cold_reduction),
        "target_percent": str(TARGET_PERCENT),
        "target_met_by_transport_container": transport_reduction >= TARGET_PERCENT,
        "target_met_by_8byte_timestamp_only": timestamp_reduction >= TARGET_PERCENT,
        "minimum_source_bytes_for_108_byte_container_at_target": minimum_source_bytes_for_target(108),
        "minimum_source_bytes_for_8_byte_timestamp_at_target": minimum_source_bytes_for_target(8),
        "minimum_source_bytes_for_1_byte_code_at_target": minimum_source_bytes_for_target(1),
        "external_model_required": meta["external_model_required"],
        "model_id": meta["model_id"],
        "unix_ns": meta["unix_ns"],
        "temporal_slot": meta["temporal_slot"],
    }
    return result


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Reproducible QTC2 proof on a real repository file."
    )
    ap.add_argument("source", type=Path)
    ap.add_argument("--unix-ns", type=int, default=1787990000000000000)
    ap.add_argument("--expected-git-sha")
    ap.add_argument("-o", "--output", type=Path)
    args = ap.parse_args()

    result = run(args.source, args.unix_ns, args.expected_git_sha)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
