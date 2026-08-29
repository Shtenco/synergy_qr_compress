from __future__ import annotations

from dataclasses import dataclass
import bz2
import hashlib
import lzma
import math
import struct
import time
import zlib
from typing import Iterable

from .rans import compress as rans_compress, decompress as rans_decompress
from .temporal import embed_temporal_tag, temporal_tag, TAG_BITS, TAG_MASK

MODEL_MAGIC = b"QD2M"
MODEL_VERSION = 1
MODEL_HEADER = struct.Struct(">4sBHHHII")
SNAPSHOT_HEADER = struct.Struct(">Q32s")
CHUNK_HEADER = struct.Struct(">Q16sI")

CONTAINER_MAGIC = b"Q3B1"
CONTAINER_VERSION = 1
CONTAINER_HEADER = struct.Struct(">4sBBBBQIIQQ32s32s")

CODEC_RAW = 0
CODEC_ZLIB = 1
CODEC_BZ2 = 2
CODEC_LZMA = 3
CODEC_BROTLI = 4
CODEC_RANS = 5
CODEC_ZSTD_DICT = 6
CODEC_GABRIEL = 7

CODEC_NAMES = {
    CODEC_RAW: "raw",
    CODEC_ZLIB: "zlib-9",
    CODEC_BZ2: "bz2-9",
    CODEC_LZMA: "lzma-extreme",
    CODEC_BROTLI: "brotli-11-refstream",
    CODEC_RANS: "rans-o0",
    CODEC_ZSTD_DICT: "zstd-19-trained-dict",
    CODEC_GABRIEL: "gabriel-horn-max",
}

_GEAR = [
    int.from_bytes(hashlib.blake2s(bytes([i]), digest_size=8, person=b"QTD2GEAR").digest(), "big")
    for i in range(256)
]


def _uvarint(value: int) -> bytes:
    if value < 0:
        raise ValueError("negative uvarint")
    out = bytearray()
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def _read_uvarint(data: bytes, pos: int) -> tuple[int, int]:
    value = shift = 0
    for _ in range(10):
        if pos >= len(data):
            raise ValueError("truncated uvarint")
        b = data[pos]
        pos += 1
        value |= (b & 0x7F) << shift
        if b < 0x80:
            return value, pos
        shift += 7
    raise ValueError("uvarint too large")


def fastcdc(data: bytes, min_size: int = 48, avg_size: int = 96, max_size: int = 192) -> list[bytes]:
    """Deterministic FastCDC-style gear chunking.

    Two masks around the target average produce an early/late normalization zone,
    which makes boundaries re-synchronize after insertions/deletions.
    """
    data = bytes(data)
    if not (1 <= min_size <= avg_size <= max_size):
        raise ValueError("require 1 <= min <= avg <= max")
    if not data:
        return []
    bits = max(1, round(math.log2(avg_size)))
    mask_early = (1 << (bits + 1)) - 1
    mask_late = (1 << max(1, bits - 1)) - 1
    out: list[bytes] = []
    start = 0
    while start < len(data):
        hard_end = min(start + max_size, len(data))
        if hard_end - start <= min_size:
            cut = hard_end
        else:
            i = start + min_size
            normal = min(start + avg_size, hard_end)
            rolling = 0
            cut = None
            while i < normal:
                rolling = ((rolling << 1) + _GEAR[data[i]]) & 0xFFFFFFFFFFFFFFFF
                i += 1
                if rolling & mask_early == 0:
                    cut = i
                    break
            if cut is None:
                while i < hard_end:
                    rolling = ((rolling << 1) + _GEAR[data[i]]) & 0xFFFFFFFFFFFFFFFF
                    i += 1
                    if rolling & mask_late == 0:
                        cut = i
                        break
            if cut is None:
                cut = hard_end
        out.append(data[start:cut])
        start = cut
    return out


@dataclass(frozen=True)
class HistoricalSnapshot:
    unix_ns: int
    data: bytes


@dataclass(frozen=True)
class ChunkEntry:
    first_seen_unix_ns: int
    digest16: bytes
    data: bytes


@dataclass(frozen=True)
class QTD2Model:
    min_size: int
    avg_size: int
    max_size: int
    snapshots: tuple[tuple[int, bytes], ...]
    chunks: tuple[ChunkEntry, ...]
    model_id: bytes

    @property
    def target_leakage_guard(self) -> set[bytes]:
        return {digest for _, digest in self.snapshots}

    def chunk_index(self) -> dict[bytes, int]:
        return {entry.digest16: i for i, entry in enumerate(self.chunks)}

    def to_bytes(self) -> bytes:
        body = bytearray(MODEL_HEADER.pack(
            MODEL_MAGIC, MODEL_VERSION, self.min_size, self.avg_size, self.max_size,
            len(self.snapshots), len(self.chunks),
        ))
        for unix_ns, digest in self.snapshots:
            body += SNAPSHOT_HEADER.pack(unix_ns, digest)
        for entry in self.chunks:
            body += CHUNK_HEADER.pack(entry.first_seen_unix_ns, entry.digest16, len(entry.data))
            body += entry.data
        return bytes(body)

    @classmethod
    def from_bytes(cls, blob: bytes) -> "QTD2Model":
        if len(blob) < MODEL_HEADER.size:
            raise ValueError("truncated QTD2 model")
        magic, version, mn, av, mx, ns, nc = MODEL_HEADER.unpack_from(blob)
        if magic != MODEL_MAGIC or version != MODEL_VERSION:
            raise ValueError("unsupported QTD2 model")
        pos = MODEL_HEADER.size
        snapshots = []
        for _ in range(ns):
            if pos + SNAPSHOT_HEADER.size > len(blob):
                raise ValueError("truncated QTD2 snapshot manifest")
            snapshots.append(SNAPSHOT_HEADER.unpack_from(blob, pos))
            pos += SNAPSHOT_HEADER.size
        chunks = []
        last_digest = None
        for _ in range(nc):
            if pos + CHUNK_HEADER.size > len(blob):
                raise ValueError("truncated QTD2 chunk")
            unix_ns, digest16, n = CHUNK_HEADER.unpack_from(blob, pos)
            pos += CHUNK_HEADER.size
            if pos + n > len(blob):
                raise ValueError("truncated QTD2 chunk payload")
            data = blob[pos:pos+n]
            pos += n
            if hashlib.blake2b(data, digest_size=16).digest() != digest16:
                raise ValueError("QTD2 chunk digest mismatch")
            if last_digest is not None and digest16 <= last_digest:
                raise ValueError("QTD2 chunk index not strictly sorted")
            last_digest = digest16
            chunks.append(ChunkEntry(unix_ns, digest16, data))
        if pos != len(blob):
            raise ValueError("trailing QTD2 model bytes")
        model_id = hashlib.sha256(blob).digest()
        return cls(mn, av, mx, tuple(snapshots), tuple(chunks), model_id)


def train_qtd2(snapshots: Iterable[HistoricalSnapshot], *, min_size: int = 48, avg_size: int = 96, max_size: int = 192) -> QTD2Model:
    normalized = sorted(
        (HistoricalSnapshot(int(s.unix_ns), bytes(s.data)) for s in snapshots),
        key=lambda s: (s.unix_ns, hashlib.sha256(s.data).digest()),
    )
    if not normalized:
        raise ValueError("at least one historical snapshot is required")
    manifest = tuple((s.unix_ns, hashlib.sha256(s.data).digest()) for s in normalized)
    bank: dict[bytes, ChunkEntry] = {}
    for snapshot in normalized:
        for chunk in fastcdc(snapshot.data, min_size, avg_size, max_size):
            digest16 = hashlib.blake2b(chunk, digest_size=16).digest()
            current = bank.get(digest16)
            if current is None or snapshot.unix_ns < current.first_seen_unix_ns:
                bank[digest16] = ChunkEntry(snapshot.unix_ns, digest16, chunk)
    chunks = tuple(bank[k] for k in sorted(bank))
    temp = QTD2Model(min_size, avg_size, max_size, manifest, chunks, b"")
    blob = temp.to_bytes()
    return QTD2Model(min_size, avg_size, max_size, manifest, chunks, hashlib.sha256(blob).digest())


def _tokenize(target: bytes, model: QTD2Model) -> tuple[bytes, int, int, int]:
    index = model.chunk_index()
    out = bytearray()
    covered = ref_count = literal_bytes = 0
    pending = bytearray()

    def flush_literal() -> None:
        nonlocal literal_bytes
        if pending:
            out.append(1)
            out.extend(_uvarint(len(pending)))
            out.extend(pending)
            literal_bytes += len(pending)
            pending.clear()

    for chunk in fastcdc(target, model.min_size, model.avg_size, model.max_size):
        digest16 = hashlib.blake2b(chunk, digest_size=16).digest()
        ref = index.get(digest16)
        if ref is None:
            pending.extend(chunk)
        else:
            flush_literal()
            out.append(0)
            out.extend(_uvarint(ref))
            covered += len(chunk)
            ref_count += 1
    flush_literal()
    return bytes(out), covered, ref_count, literal_bytes


def _detokenize(tokens: bytes, model: QTD2Model, expected_size: int) -> bytes:
    out = bytearray()
    pos = 0
    while pos < len(tokens):
        kind = tokens[pos]
        pos += 1
        if kind == 0:
            ref, pos = _read_uvarint(tokens, pos)
            if ref >= len(model.chunks):
                raise ValueError("QTD2 chunk reference out of range")
            out += model.chunks[ref].data
        elif kind == 1:
            n, pos = _read_uvarint(tokens, pos)
            if pos + n > len(tokens):
                raise ValueError("truncated QTD2 literal")
            out += tokens[pos:pos+n]
            pos += n
        else:
            raise ValueError("unknown QTD2 token")
        if len(out) > expected_size:
            raise ValueError("QTD2 output exceeds target size")
    if len(out) != expected_size:
        raise ValueError("QTD2 output size mismatch")
    return bytes(out)


def _zstd_dict(model: QTD2Model):
    try:
        import zstandard as zstd
    except Exception:
        return None, None
    samples = [entry.data for entry in model.chunks if len(entry.data) >= 8]
    if len(samples) < 8 or sum(map(len, samples)) < 1024:
        return zstd, None
    dict_size = min(8192, max(256, sum(map(len, samples)) // 3))
    try:
        trained = zstd.train_dictionary(dict_size, samples)
        return zstd, trained
    except Exception:
        return zstd, None


def _gabriel_engine():
    try:
        from compression_lab.gabriel_horn_engine import GabrielHornEngine
        return GabrielHornEngine(profile="max", surface_weight=0.0, work_weight=0.0)
    except Exception:
        try:
            from gabriel_horn_engine import GabrielHornEngine
            return GabrielHornEngine(profile="max", surface_weight=0.0, work_weight=0.0)
        except Exception:
            return None


def _compress_candidates(tokens: bytes, model: QTD2Model) -> list[tuple[int, bytes]]:
    candidates = [
        (CODEC_RAW, tokens),
        (CODEC_ZLIB, zlib.compress(tokens, 9)),
        (CODEC_BZ2, bz2.compress(tokens, 9)),
        (CODEC_LZMA, lzma.compress(tokens, preset=9 | lzma.PRESET_EXTREME)),
        (CODEC_RANS, rans_compress(tokens)),
    ]
    try:
        import brotli
        candidates.append((CODEC_BROTLI, brotli.compress(tokens, quality=11, mode=brotli.MODE_GENERIC)))
    except Exception:
        pass
    zstd, trained = _zstd_dict(model)
    if zstd is not None:
        try:
            if trained is not None:
                cctx = zstd.ZstdCompressor(level=19, dict_data=trained, write_checksum=True, write_content_size=True)
            else:
                cctx = zstd.ZstdCompressor(level=19, write_checksum=True, write_content_size=True)
            candidates.append((CODEC_ZSTD_DICT, cctx.compress(tokens)))
        except Exception:
            pass
    gabriel = _gabriel_engine()
    if gabriel is not None:
        try:
            archive = gabriel.compress(tokens)
            if gabriel.decompress(archive) == tokens:
                candidates.append((CODEC_GABRIEL, archive))
        except Exception:
            pass
    return candidates


def _decompress_payload(codec: int, payload: bytes, model: QTD2Model, token_size: int) -> bytes:
    if codec == CODEC_RAW:
        result = payload
    elif codec == CODEC_ZLIB:
        result = zlib.decompress(payload)
    elif codec == CODEC_BZ2:
        result = bz2.decompress(payload)
    elif codec == CODEC_LZMA:
        result = lzma.decompress(payload)
    elif codec == CODEC_RANS:
        result = rans_decompress(payload)
    elif codec == CODEC_BROTLI:
        import brotli
        result = brotli.decompress(payload)
    elif codec == CODEC_ZSTD_DICT:
        import zstandard as zstd
        _, trained = _zstd_dict(model)
        if trained is not None:
            dctx = zstd.ZstdDecompressor(dict_data=trained)
        else:
            dctx = zstd.ZstdDecompressor()
        result = dctx.decompress(payload, max_output_size=token_size)
    elif codec == CODEC_GABRIEL:
        gabriel = _gabriel_engine()
        if gabriel is None:
            raise ValueError("Gabriel codec unavailable")
        result = gabriel.decompress(payload)
    else:
        raise ValueError("unknown QTD2 payload codec")
    if len(result) != token_size:
        raise ValueError("QTD2 token stream size mismatch")
    return result


@dataclass(frozen=True)
class PackedBlind:
    blob: bytes
    codec_id: int
    unix_ns: int
    original_size: int
    covered_bytes: int
    literal_bytes: int
    ref_count: int
    token_size: int
    payload_size: int

    @property
    def coverage_percent(self) -> float:
        return 100.0 if self.original_size == 0 else 100.0 * self.covered_bytes / self.original_size


def pack_blind(target: bytes, model: QTD2Model, *, unix_ns: int | None = None) -> PackedBlind:
    target = bytes(target)
    digest = hashlib.sha256(target).digest()
    if digest in model.target_leakage_guard:
        raise ValueError("blind benchmark violation: target SHA-256 exists in training snapshots")
    tokens, covered, refs, literal_bytes = _tokenize(target, model)
    candidates = _compress_candidates(tokens, model)
    valid: list[tuple[int, bytes]] = []
    for codec, payload in candidates:
        try:
            if _decompress_payload(codec, payload, model, len(tokens)) == tokens:
                valid.append((codec, payload))
        except Exception:
            pass
    if not valid:
        raise RuntimeError("no valid QTD2 residual codec")
    codec, payload = min(valid, key=lambda item: (len(item[1]), item[0]))
    anchor = embed_temporal_tag(digest, unix_ns if unix_ns is not None else time.time_ns())
    flags = TAG_BITS
    header = CONTAINER_HEADER.pack(
        CONTAINER_MAGIC, CONTAINER_VERSION, codec, flags, 0,
        anchor.adjusted_unix_ns, len(target), len(tokens), len(payload), covered,
        model.model_id, digest,
    )
    return PackedBlind(header + payload, codec, anchor.adjusted_unix_ns, len(target), covered, literal_bytes, refs, len(tokens), len(payload))


def unpack_blind(blob: bytes, model: QTD2Model) -> bytes:
    if len(blob) < CONTAINER_HEADER.size:
        raise ValueError("truncated QTD2 blind container")
    magic, version, codec, flags, _, unix_ns, original_size, token_size, payload_size, covered, model_id, digest = CONTAINER_HEADER.unpack_from(blob)
    if magic != CONTAINER_MAGIC or version != CONTAINER_VERSION:
        raise ValueError("unsupported QTD2 blind container")
    if flags != TAG_BITS:
        raise ValueError("unsupported temporal tag width")
    if model_id != model.model_id:
        raise ValueError("QTD2 model_id mismatch")
    if unix_ns & TAG_MASK != temporal_tag(digest):
        raise ValueError("QTD2 temporal digest tag mismatch")
    payload = blob[CONTAINER_HEADER.size:]
    if len(payload) != payload_size:
        raise ValueError("QTD2 payload length mismatch")
    tokens = _decompress_payload(codec, payload, model, token_size)
    result = _detokenize(tokens, model, original_size)
    if hashlib.sha256(result).digest() != digest:
        raise ValueError("QTD2 target SHA-256 mismatch")
    return result


def inspect_blind(blob: bytes, model: QTD2Model | None = None) -> dict:
    if len(blob) < CONTAINER_HEADER.size:
        raise ValueError("truncated QTD2 blind container")
    magic, version, codec, flags, _, unix_ns, original_size, token_size, payload_size, covered, model_id, digest = CONTAINER_HEADER.unpack_from(blob)
    if magic != CONTAINER_MAGIC or version != CONTAINER_VERSION:
        raise ValueError("unsupported QTD2 blind container")
    return {
        "magic": "Q3B1",
        "version": version,
        "codec_id": codec,
        "codec": CODEC_NAMES.get(codec, "unknown"),
        "original_size": original_size,
        "token_size": token_size,
        "payload_size": payload_size,
        "container_size": len(blob),
        "covered_bytes": covered,
        "model_coverage_percent": 100.0 if original_size == 0 else 100.0 * covered / original_size,
        "transport_reduction_percent": 100.0 if original_size == 0 else 100.0 * (1.0 - len(blob) / original_size),
        "model_id": model_id.hex(),
        "model_id_matches": None if model is None else model.model_id == model_id,
        "target_sha256": digest.hex(),
        "target_sha_absent_from_training": None if model is None else digest not in model.target_leakage_guard,
        "unix_ns": unix_ns,
        "temporal_slot": unix_ns >> TAG_BITS,
        "shared_brotli_rfc9841": False,
        "shared_context_note": "Brotli, when selected, compresses the chunk-reference residual stream; Python brotli does not expose RFC 9841 shared-dictionary APIs.",
    }
