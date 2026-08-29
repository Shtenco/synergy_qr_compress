from __future__ import annotations
from collections import Counter
import bisect
import struct

RANS_BYTE_L = 1 << 23
SCALE_BITS = 12
TOTFREQ = 1 << SCALE_BITS
MAGIC = b"RA1"

def _normalize(data: bytes) -> dict[int, int]:
    if not data:
        return {}
    counts = Counter(data)
    freqs: dict[int, int] = {}
    remainders: list[tuple[int, int]] = []
    n = len(data)
    for symbol, count in counts.items():
        scaled = count * TOTFREQ
        freq = max(1, scaled // n)
        freqs[symbol] = freq
        remainders.append((scaled % n, symbol))
    total = sum(freqs.values())
    if total < TOTFREQ:
        order = [s for _, s in sorted(remainders, reverse=True)]
        i = 0
        while total < TOTFREQ:
            freqs[order[i % len(order)]] += 1
            total += 1
            i += 1
    elif total > TOTFREQ:
        order = [s for _, s in sorted(remainders)]
        i = 0
        while total > TOTFREQ:
            s = order[i % len(order)]
            if freqs[s] > 1:
                freqs[s] -= 1
                total -= 1
            i += 1
    return freqs

def compress(data: bytes) -> bytes:
    data = bytes(data)
    freqs = _normalize(data)
    cum: dict[int, int] = {}
    cur = 0
    for s in sorted(freqs):
        cum[s] = cur
        cur += freqs[s]
    state = RANS_BYTE_L
    renorm: list[int] = []
    for s in reversed(data):
        freq = freqs[s]
        start = cum[s]
        x_max = ((RANS_BYTE_L >> SCALE_BITS) << 8) * freq
        while state >= x_max:
            renorm.append(state & 0xFF)
            state >>= 8
        state = ((state // freq) << SCALE_BITS) + (state % freq) + start
    out = bytearray(MAGIC)
    out += struct.pack(">QH", len(data), len(freqs))
    for s in sorted(freqs):
        out += bytes([s]) + struct.pack(">H", freqs[s])
    out += struct.pack("<I", state)
    out += bytes(reversed(renorm))
    return bytes(out)

def decompress(blob: bytes) -> bytes:
    if len(blob) < 17 or blob[:3] != MAGIC:
        raise ValueError("invalid rANS stream")
    n, symbol_count = struct.unpack_from(">QH", blob, 3)
    if symbol_count > 256:
        raise ValueError("invalid rANS symbol count")
    pos = 13
    freqs: dict[int, int] = {}
    for _ in range(symbol_count):
        if pos + 3 > len(blob):
            raise ValueError("truncated rANS table")
        s = blob[pos]
        f = struct.unpack_from(">H", blob, pos + 1)[0]
        pos += 3
        if f == 0 or s in freqs:
            raise ValueError("invalid rANS frequency table")
        freqs[s] = f
    if sum(freqs.values()) not in (0, TOTFREQ):
        raise ValueError("rANS frequencies do not normalize")
    if pos + 4 > len(blob):
        raise ValueError("truncated rANS state")
    state = struct.unpack_from("<I", blob, pos)[0]
    pos += 4
    starts: list[int] = []
    symbols: list[int] = []
    cum: dict[int, int] = {}
    cur = 0
    for s in sorted(freqs):
        starts.append(cur)
        symbols.append(s)
        cum[s] = cur
        cur += freqs[s]
    out = bytearray()
    for _ in range(n):
        if not symbols:
            raise ValueError("empty rANS alphabet for non-empty payload")
        x = state & (TOTFREQ - 1)
        idx = bisect.bisect_right(starts, x) - 1
        if idx < 0:
            raise ValueError("rANS cumulative lookup failed")
        s = symbols[idx]
        start = cum[s]
        freq = freqs[s]
        if x >= start + freq:
            raise ValueError("rANS cumulative range mismatch")
        out.append(s)
        state = freq * (state >> SCALE_BITS) + (x - start)
        while state < RANS_BYTE_L:
            if pos >= len(blob):
                raise ValueError("truncated rANS renormalization bytes")
            state = (state << 8) | blob[pos]
            pos += 1
    if pos != len(blob):
        raise ValueError("trailing bytes in rANS stream")
    return bytes(out)
