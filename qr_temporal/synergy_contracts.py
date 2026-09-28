from __future__ import annotations
from hashlib import sha256
from typing import Any

from .qtd3 import RepoBlob, train_qtd3, pack_blind_v3, unpack_v3, inspect_v3

CONTRACT_ID = "synergy.archive.benchmark-evidence/v1"
AUTHORITY = "compression_benchmark"


def lossless_benchmark_payload(
    *,
    benchmark_id: str,
    training_blobs: list[RepoBlob],
    target: bytes,
    path: str,
    target_unix_ns: int,
) -> dict[str, Any]:
    if not benchmark_id.strip() or not target:
        raise ValueError("benchmark_id and target required")
    model = train_qtd3(training_blobs)
    packed = pack_blind_v3(target, path, model, unix_ns=target_unix_ns)
    restored = unpack_v3(packed.blob, model)
    if restored != target:
        raise ValueError("lossless round-trip failed")
    info = inspect_v3(packed.blob, model)
    return {
        "benchmark_id": benchmark_id,
        "target_sha256": sha256(target).hexdigest(),
        "model_id16": info["model_id16"],
        "original_bytes": len(target),
        "container_bytes": len(packed.blob),
        "covered_bytes": packed.covered_bytes,
        "round_trip_verified": True,
        "temporal_cutoff_valid": bool(info["temporal_cutoff_valid"]),
        "transport_reduction_percent": float(info["transport_reduction_percent"]),
        "deployment_authority": False,
    }
