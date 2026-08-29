from __future__ import annotations
from dataclasses import dataclass
import hashlib, struct, time
from .codec import choose_best, decode_payload, codec_name
from .model import TemporalDictionary, TemporalEntry
from .residual import build_patch, apply_patch
from .temporal import TAG_BITS, TAG_MASK, embed_temporal_tag, temporal_tag

MAGIC = b"QTC2"
VERSION = 2
MODE_PATCH = 0
MODE_STANDALONE = 1
MODE_EXACT = 2
HEADER = struct.Struct(">4sBBBBB3xQQIIQ32s32s")

@dataclass(frozen=True)
class PackedV2:
    blob: bytes
    unix_ns: int
    mode: int
    codec_id: int
    transform_id: int
    original_size: int
    payload_size: int
    covered_size: int
    model_id: bytes
    @property
    def coverage_percent(self) -> float:
        if self.mode == MODE_STANDALONE:
            return 0.0
        return 100.0 if self.original_size == 0 else 100.0 * self.covered_size / self.original_size

def _digest_tag(digest: bytes) -> int:
    return temporal_tag(digest)

def _timestamp_for_entry(entry: TemporalEntry, digest: bytes) -> int:
    return (entry.slot << TAG_BITS) | _digest_tag(digest)

def _verify_timestamp_digest(unix_ns: int, digest: bytes) -> bool:
    return (unix_ns & TAG_MASK) == _digest_tag(digest)

def pack_v2(data: bytes, model: TemporalDictionary | None = None, unix_ns: int | None = None, candidate_limit: int = 8) -> PackedV2:
    data = bytes(data)
    digest = hashlib.sha256(data).digest()
    standalone = choose_best(data)
    standalone_anchor = embed_temporal_tag(digest, unix_ns if unix_ns is not None else time.time_ns())
    best_mode = MODE_STANDALONE
    best_codec = standalone.codec_id
    best_transform = standalone.transform_id
    best_payload = standalone.payload
    best_unix_ns = standalone_anchor.adjusted_unix_ns
    best_covered = 0
    best_template_size = 0
    best_model_id = bytes(32)
    if model is not None:
        exact = next((e for e in model.entries if e.digest == digest and len(e.data) == len(data)), None)
        if exact is not None:
            best_mode = MODE_EXACT
            best_codec = 0
            best_transform = 0
            best_payload = b""
            best_unix_ns = _timestamp_for_entry(exact, digest)
            best_covered = len(data)
            best_template_size = len(exact.data)
            best_model_id = model.model_id
        else:
            for entry in model.candidates(data, unix_ns=unix_ns, limit=candidate_limit):
                patch = build_patch(entry.data, data)
                c = choose_best(patch.blob)
                if len(c.payload) < len(best_payload):
                    best_mode = MODE_PATCH
                    best_codec = c.codec_id
                    best_transform = c.transform_id
                    best_payload = c.payload
                    best_unix_ns = _timestamp_for_entry(entry, digest)
                    best_covered = patch.covered_bytes
                    best_template_size = len(entry.data)
                    best_model_id = model.model_id
    header = HEADER.pack(
        MAGIC, VERSION, best_mode, best_codec, best_transform, TAG_BITS,
        best_unix_ns, len(data), len(best_payload), best_template_size,
        best_covered, best_model_id, digest,
    )
    return PackedV2(
        header+best_payload, best_unix_ns, best_mode, best_codec, best_transform,
        len(data), len(best_payload), best_covered, best_model_id,
    )

def unpack_v2(blob: bytes, model: TemporalDictionary | None = None) -> bytes:
    meta = _parse(blob)
    payload = blob[HEADER.size:]
    if len(payload) != meta["payload_size"]:
        raise ValueError("payload length mismatch")
    if not _verify_timestamp_digest(meta["unix_ns"], meta["digest"]):
        raise ValueError("QTC2 temporal digest tag mismatch")
    mode = meta["mode"]
    if mode == MODE_STANDALONE:
        data = decode_payload(payload, meta["codec_id"], meta["transform_id"])
    else:
        if model is None:
            raise ValueError("QTC2 model is required for temporal decode")
        if model.model_id != meta["model_id"]:
            raise ValueError("QTC2 model_id mismatch")
        try:
            entry = model.get_by_address(meta["unix_ns"])
        except KeyError as e:
            raise ValueError(str(e)) from e
        if len(entry.data) != meta["template_size"]:
            raise ValueError("QTC2 template size mismatch")
        if mode == MODE_EXACT:
            if payload:
                raise ValueError("QTC2 exact mode must have empty payload")
            data = entry.data
        elif mode == MODE_PATCH:
            patch = decode_payload(payload, meta["codec_id"], meta["transform_id"])
            data = apply_patch(entry.data, patch)
        else:
            raise ValueError(f"unknown QTC2 mode {mode}")
    if len(data) != meta["original_size"]:
        raise ValueError("QTC2 original length mismatch")
    if hashlib.sha256(data).digest() != meta["digest"]:
        raise ValueError("QTC2 SHA-256 mismatch")
    return data

def _parse(blob: bytes) -> dict:
    if len(blob) < HEADER.size:
        raise ValueError("truncated QTC2 container")
    values = HEADER.unpack_from(blob)
    magic, version, mode, codec_id, transform_id, tag_bits, unix_ns, original_size, payload_size, template_size, covered_size, model_id, digest = values
    if magic != MAGIC or version != VERSION:
        raise ValueError("unsupported QTC2 container")
    if tag_bits != TAG_BITS:
        raise ValueError("unsupported QTC2 temporal tag width")
    return {
        "magic": magic, "version": version, "mode": mode, "codec_id": codec_id,
        "transform_id": transform_id, "tag_bits": tag_bits, "unix_ns": unix_ns,
        "original_size": original_size, "payload_size": payload_size,
        "template_size": template_size, "covered_size": covered_size,
        "model_id": model_id, "digest": digest,
    }

def inspect_v2(blob: bytes, model: TemporalDictionary | None = None) -> dict:
    m = _parse(blob)
    mode_name = {MODE_PATCH:"patch", MODE_STANDALONE:"standalone", MODE_EXACT:"exact"}.get(m["mode"], "unknown")
    coverage = 0.0 if m["mode"] == MODE_STANDALONE else (100.0 if m["original_size"] == 0 else 100.0*m["covered_size"]/m["original_size"])
    model_ok = None
    slot_present = None
    if m["mode"] != MODE_STANDALONE and model is not None:
        model_ok = model.model_id == m["model_id"]
        if model_ok:
            try:
                model.get_by_address(m["unix_ns"])
                slot_present = True
            except KeyError:
                slot_present = False
    return {
        "magic":"QTC2", "version":2, "mode":mode_name,
        "codec_id":m["codec_id"], "codec":codec_name(m["codec_id"]),
        "transform_id":m["transform_id"], "unix_ns":m["unix_ns"],
        "temporal_slot":m["unix_ns"] >> TAG_BITS,
        "temporal_tag_bits":TAG_BITS,
        "temporal_digest_tag_valid":_verify_timestamp_digest(m["unix_ns"], m["digest"]),
        "original_size":m["original_size"], "template_size":m["template_size"],
        "covered_size":m["covered_size"], "model_coverage_percent":coverage,
        "target_99_9999_percent_met":coverage >= 99.9999,
        "payload_size":m["payload_size"], "container_size":len(blob),
        "payload_reduction_vs_original_percent": (100.0*(1-m["payload_size"]/m["original_size"])) if m["original_size"] else 100.0,
        "external_model_required":m["mode"] != MODE_STANDALONE,
        "model_id":m["model_id"].hex(), "model_id_matches":model_ok,
        "temporal_slot_present":slot_present, "sha256":m["digest"].hex(),
    }
