from __future__ import annotations
from dataclasses import dataclass
import bz2, lzma, time, zlib
from typing import Callable
from . import rans as _rans

CodecTuple = tuple[str, Callable[[bytes], bytes], Callable[[bytes], bytes]]

CODECS: dict[int, CodecTuple] = {
    0: ("raw", lambda b: b, lambda b: b),
    1: ("zlib-9", lambda b: zlib.compress(b, 9), zlib.decompress),
    2: ("bz2-9", lambda b: bz2.compress(b, 9), bz2.decompress),
    3: ("lzma-9", lambda b: lzma.compress(b, preset=9 | lzma.PRESET_EXTREME), lzma.decompress),
    6: ("rans-o0", _rans.compress, _rans.decompress),
}

try:
    import zstandard as _zstd
except ImportError:
    _zstd = None
else:
    CODECS[4] = (
        "zstd-19",
        lambda b: _zstd.ZstdCompressor(level=19).compress(b),
        lambda b: _zstd.ZstdDecompressor().decompress(b),
    )

try:
    import brotli as _brotli
except ImportError:
    _brotli = None
else:
    CODECS[5] = (
        "brotli-11",
        lambda b: _brotli.compress(b, quality=11),
        _brotli.decompress,
    )

try:
    from compression_lab.gabriel_horn_engine import GabrielHornEngine as _GabrielHornEngine
except Exception:
    _GabrielHornEngine = None
else:
    _gabriel = _GabrielHornEngine(profile="max")
    CODECS[7] = ("gabriel-horn-max", _gabriel.compress, _gabriel.decompress)

TRANSFORMS = {0: "identity", 1: "delta8"}

def delta8_encode(data: bytes) -> bytes:
    if not data: return b""
    out = bytearray(len(data)); prev = 0
    for i, x in enumerate(data):
        out[i] = (x - prev) & 0xFF; prev = x
    return bytes(out)

def delta8_decode(data: bytes) -> bytes:
    out = bytearray(len(data)); prev = 0
    for i, x in enumerate(data):
        prev = (prev + x) & 0xFF; out[i] = prev
    return bytes(out)

def apply_transform(data: bytes, transform_id: int) -> bytes:
    if transform_id == 0: return data
    if transform_id == 1: return delta8_encode(data)
    raise ValueError(f"unknown transform {transform_id}")

def undo_transform(data: bytes, transform_id: int) -> bytes:
    if transform_id == 0: return data
    if transform_id == 1: return delta8_decode(data)
    raise ValueError(f"unknown transform {transform_id}")

@dataclass(frozen=True)
class Candidate:
    codec_id: int
    transform_id: int
    payload: bytes
    encode_ms: float
    decode_ms: float
    @property
    def score(self) -> float:
        return len(self.payload) + 0.02 * self.encode_ms + 0.02 * self.decode_ms

def choose_best(data: bytes) -> Candidate:
    candidates = []
    for transform_id in TRANSFORMS:
        transformed = apply_transform(data, transform_id)
        for codec_id, (_, enc, dec) in CODECS.items():
            try:
                t0 = time.perf_counter(); payload = enc(transformed); t1 = time.perf_counter()
                restored = dec(payload); t2 = time.perf_counter()
            except Exception:
                continue
            if restored != transformed:
                continue
            candidates.append(Candidate(codec_id, transform_id, payload, (t1-t0)*1000, (t2-t1)*1000))
    if not candidates:
        raise RuntimeError("no valid codec candidate")
    return min(candidates, key=lambda c: c.score)

def decode_payload(payload: bytes, codec_id: int, transform_id: int) -> bytes:
    try:
        dec = CODECS[codec_id][2]
    except KeyError as e:
        raise ValueError(f"codec {codec_id} is unavailable in this environment") from e
    return undo_transform(dec(payload), transform_id)

def codec_name(codec_id: int) -> str:
    return CODECS.get(codec_id, (f"unknown-{codec_id}", None, None))[0]
