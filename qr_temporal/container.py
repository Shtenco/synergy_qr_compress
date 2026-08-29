from __future__ import annotations
from dataclasses import dataclass
import hashlib, struct
from .codec import choose_best, decode_payload
from .temporal import embed_temporal_tag, verify_temporal_tag

MAGIC = b"QTC1"; VERSION = 1
HEADER = struct.Struct(">4sBBBBQQI32s")

@dataclass(frozen=True)
class Packed:
    blob: bytes
    unix_ns: int
    codec_id: int
    transform_id: int
    original_size: int
    payload_size: int

def pack(data: bytes, unix_ns: int | None = None) -> Packed:
    c = choose_best(data); anchor = embed_temporal_tag(c.payload, unix_ns); digest = hashlib.sha256(data).digest()
    header = HEADER.pack(MAGIC, VERSION, c.codec_id, c.transform_id, 0, anchor.adjusted_unix_ns, len(data), len(c.payload), digest)
    return Packed(header+c.payload, anchor.adjusted_unix_ns, c.codec_id, c.transform_id, len(data), len(c.payload))

def unpack(blob: bytes) -> bytes:
    if len(blob) < HEADER.size: raise ValueError("truncated container")
    magic, version, codec_id, transform_id, flags, unix_ns, original_size, payload_size, digest = HEADER.unpack_from(blob)
    if magic != MAGIC or version != VERSION: raise ValueError("unsupported container")
    payload = blob[HEADER.size:]
    if len(payload) != payload_size: raise ValueError("payload length mismatch")
    if not verify_temporal_tag(payload, unix_ns): raise ValueError("temporal tag mismatch")
    data = decode_payload(payload, codec_id, transform_id)
    if len(data) != original_size: raise ValueError("original length mismatch")
    if hashlib.sha256(data).digest() != digest: raise ValueError("SHA-256 mismatch")
    return data

def inspect(blob: bytes) -> dict:
    if len(blob) < HEADER.size: raise ValueError("truncated container")
    magic, version, codec_id, transform_id, flags, unix_ns, original_size, payload_size, digest = HEADER.unpack_from(blob)
    return {"magic": magic.decode("ascii", "replace"), "version": version, "codec_id": codec_id, "transform_id": transform_id, "unix_ns": unix_ns, "original_size": original_size, "payload_size": payload_size, "container_size": len(blob), "ratio": (original_size/len(blob)) if blob else 0.0, "sha256": digest.hex(), "temporal_tag_valid": verify_temporal_tag(blob[HEADER.size:], unix_ns)}
