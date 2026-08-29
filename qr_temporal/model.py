from __future__ import annotations
from dataclasses import dataclass
import hashlib
import struct
from pathlib import Path
from typing import Iterable
from .temporal import TAG_BITS, temporal_tag

MODEL_MAGIC = b"QTD1"
MODEL_VERSION = 1
MODEL_HEADER = struct.Struct(">4sBI")
ENTRY_HEADER = struct.Struct(">QQQI32s")
MAX_ENTRIES = 1_000_000
MAX_ENTRY_SIZE = 1 << 30

@dataclass(frozen=True)
class TemporalSample:
    unix_ns: int
    data: bytes

@dataclass(frozen=True)
class TemporalEntry:
    slot: int
    source_unix_ns: int
    sketch64: int
    digest: bytes
    data: bytes
    @property
    def address_base(self) -> int:
        return self.slot << TAG_BITS
    def address_for(self, content_digest: bytes) -> int:
        return self.address_base | temporal_tag(content_digest)

@dataclass(frozen=True)
class TemporalDictionary:
    entries: tuple[TemporalEntry, ...]
    model_id: bytes

    def get_by_address(self, unix_ns: int) -> TemporalEntry:
        slot = unix_ns >> TAG_BITS
        lo, hi = 0, len(self.entries)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.entries[mid].slot < slot:
                lo = mid + 1
            else:
                hi = mid
        if lo < len(self.entries) and self.entries[lo].slot == slot:
            return self.entries[lo]
        raise KeyError(f"temporal slot {slot} not present in model")

    def candidates(self, data: bytes, unix_ns: int | None = None, limit: int = 8) -> list[TemporalEntry]:
        if not self.entries:
            return []
        target_sketch = sketch64(data)
        requested_slot = (unix_ns >> TAG_BITS) if unix_ns is not None else None
        def rank(e: TemporalEntry) -> tuple[int, int, int]:
            hamming = (e.sketch64 ^ target_sketch).bit_count()
            temporal = abs(e.slot-requested_slot) if requested_slot is not None else 0
            size_delta = abs(len(e.data)-len(data))
            return (hamming, min(temporal, 1 << 62), size_delta)
        return sorted(self.entries, key=rank)[:max(1, limit)]

    def to_bytes(self) -> bytes:
        return _serialize_entries(self.entries)

    def save(self, path: str | Path) -> None:
        Path(path).write_bytes(self.to_bytes())

    @classmethod
    def from_bytes(cls, blob: bytes) -> "TemporalDictionary":
        if len(blob) < MODEL_HEADER.size:
            raise ValueError("truncated temporal model")
        magic, version, count = MODEL_HEADER.unpack_from(blob)
        if magic != MODEL_MAGIC or version != MODEL_VERSION:
            raise ValueError("unsupported temporal model")
        if count > MAX_ENTRIES:
            raise ValueError("temporal model entry limit exceeded")
        pos = MODEL_HEADER.size
        entries: list[TemporalEntry] = []
        last_slot = -1
        for _ in range(count):
            if pos + ENTRY_HEADER.size > len(blob):
                raise ValueError("truncated temporal model entry")
            slot, source_unix_ns, sketch, n, digest = ENTRY_HEADER.unpack_from(blob, pos)
            pos += ENTRY_HEADER.size
            if n > MAX_ENTRY_SIZE or pos+n > len(blob):
                raise ValueError("invalid temporal model entry size")
            data = blob[pos:pos+n]
            pos += n
            if hashlib.sha256(data).digest() != digest:
                raise ValueError("temporal model entry SHA-256 mismatch")
            if slot <= last_slot:
                raise ValueError("temporal model slots must be strictly increasing")
            last_slot = slot
            entries.append(TemporalEntry(slot, source_unix_ns, sketch, digest, data))
        if pos != len(blob):
            raise ValueError("trailing bytes in temporal model")
        model_id = hashlib.sha256(blob).digest()
        return cls(tuple(entries), model_id)

    @classmethod
    def load(cls, path: str | Path) -> "TemporalDictionary":
        return cls.from_bytes(Path(path).read_bytes())

def sketch64(data: bytes) -> int:
    if not data:
        return 0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    votes = [0] * 64
    for value, count in enumerate(counts):
        if not count:
            continue
        h = int.from_bytes(hashlib.blake2b(bytes([value]), digest_size=8, person=b"QTC2SIM").digest(), "big")
        for bit in range(64):
            votes[bit] += count if ((h >> bit) & 1) else -count
    out = 0
    for bit, vote in enumerate(votes):
        if vote >= 0:
            out |= 1 << bit
    return out

def _serialize_entries(entries) -> bytes:
    ordered = sorted(entries, key=lambda e: e.slot)
    out = bytearray(MODEL_HEADER.pack(MODEL_MAGIC, MODEL_VERSION, len(ordered)))
    for e in ordered:
        out += ENTRY_HEADER.pack(e.slot, e.source_unix_ns, e.sketch64, len(e.data), e.digest)
        out += e.data
    return bytes(out)

def train_temporal_dictionary(samples: Iterable[TemporalSample]) -> TemporalDictionary:
    normalized = sorted(
        (TemporalSample(int(s.unix_ns), bytes(s.data)) for s in samples),
        key=lambda s: (s.unix_ns, hashlib.sha256(s.data).digest()),
    )
    if not normalized:
        raise ValueError("at least one training sample is required")
    used: set[int] = set()
    entries: list[TemporalEntry] = []
    for s in normalized:
        slot = max(0, s.unix_ns >> TAG_BITS)
        while slot in used:
            slot += 1
        used.add(slot)
        digest = hashlib.sha256(s.data).digest()
        entries.append(TemporalEntry(slot, s.unix_ns, sketch64(s.data), digest, s.data))
    entries = sorted(entries, key=lambda e: e.slot)
    blob = _serialize_entries(entries)
    return TemporalDictionary(tuple(entries), hashlib.sha256(blob).digest())

def samples_from_paths(paths: Iterable[str | Path]) -> list[TemporalSample]:
    out = []
    for raw in paths:
        p = Path(raw)
        st = p.stat()
        out.append(TemporalSample(st.st_mtime_ns, p.read_bytes()))
    return out
