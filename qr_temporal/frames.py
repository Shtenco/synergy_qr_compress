from __future__ import annotations
from dataclasses import dataclass
import binascii, math, struct

FRAME_MAGIC = b"QF1"
FRAME_HEADER = struct.Struct(">3sQHHII")

@dataclass(frozen=True)
class Frame:
    index: int
    total: int
    unix_ns: int
    bytes: bytes

def split_frames(blob: bytes, unix_ns: int, max_frame_bytes: int = 2200) -> list[Frame]:
    if max_frame_bytes <= FRAME_HEADER.size: raise ValueError("max_frame_bytes too small")
    chunk_size = max_frame_bytes - FRAME_HEADER.size; total = max(1, math.ceil(len(blob)/chunk_size))
    if total > 65535: raise ValueError("too many QR frames")
    out = []
    for i in range(total):
        chunk = blob[i*chunk_size:(i+1)*chunk_size]; crc = binascii.crc32(chunk) & 0xffffffff
        header = FRAME_HEADER.pack(FRAME_MAGIC, unix_ns, i, total, len(chunk), crc)
        out.append(Frame(i, total, unix_ns, header+chunk))
    return out

def join_frames(frames: list[bytes]) -> tuple[int, bytes]:
    if not frames: raise ValueError("no frames")
    parsed = {}; expected_total = None; unix_ns = None
    for raw in frames:
        if len(raw) < FRAME_HEADER.size: raise ValueError("truncated frame")
        magic, ts, idx, total, n, crc = FRAME_HEADER.unpack_from(raw); chunk = raw[FRAME_HEADER.size:]
        if magic != FRAME_MAGIC: raise ValueError("bad frame magic")
        if len(chunk) != n or (binascii.crc32(chunk) & 0xffffffff) != crc: raise ValueError("frame CRC mismatch")
        if expected_total is None: expected_total, unix_ns = total, ts
        if total != expected_total or ts != unix_ns: raise ValueError("mixed frame set")
        parsed[idx] = chunk
    if len(parsed) != expected_total or set(parsed) != set(range(expected_total)): raise ValueError("missing frame")
    return unix_ns, b"".join(parsed[i] for i in range(expected_total))
