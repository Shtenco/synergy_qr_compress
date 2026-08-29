from __future__ import annotations
from dataclasses import dataclass
import hashlib, time

TAG_BITS = 20
TAG_MASK = (1 << TAG_BITS) - 1

@dataclass(frozen=True)
class TemporalAnchor:
    unix_ns: int
    adjusted_unix_ns: int
    tag: int
    adjustment_ns: int

def _tag(data: bytes) -> int:
    return int.from_bytes(hashlib.blake2s(data, digest_size=4).digest(), "big") & TAG_MASK

def embed_temporal_tag(data: bytes, unix_ns: int | None = None) -> TemporalAnchor:
    if unix_ns is None: unix_ns = time.time_ns()
    tag = _tag(data); base = unix_ns & ~TAG_MASK; candidate = base | tag; step = 1 << TAG_BITS
    choices = (candidate-step, candidate, candidate+step)
    adjusted = min(choices, key=lambda x: abs(x-unix_ns))
    return TemporalAnchor(unix_ns, adjusted, tag, adjusted-unix_ns)

def verify_temporal_tag(data: bytes, adjusted_unix_ns: int) -> bool:
    return (adjusted_unix_ns & TAG_MASK) == _tag(data)

def temporal_coverage_bits(payload: bytes, adjusted_unix_ns: int) -> dict:
    payload_bits = max(1, len(payload) * 8); carried = min(TAG_BITS, payload_bits)
    return {"timestamp_bits": carried, "payload_bits": payload_bits, "coverage_fraction": carried/payload_bits, "coverage_percent": 100.0*carried/payload_bits, "tag_valid": verify_temporal_tag(payload, adjusted_unix_ns)}
