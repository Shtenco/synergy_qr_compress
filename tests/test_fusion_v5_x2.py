import hashlib
import random
import zlib

from qr_temporal import fusion_v5_x2 as v5


def _rt(data: bytes) -> bytes:
    archive = v5.compress(data)
    restored = v5.decompress(archive)
    assert restored == data
    assert hashlib.sha256(restored).digest() == hashlib.sha256(data).digest()
    return archive


def test_roundtrip_basic():
    rng = random.Random(123)
    cases = [
        b"",
        b"a",
        b"hello world" * 100,
        bytes(range(256)) * 16,
        bytes([0]) * 8192,
        b"abc123XYZ\n" * 1000,
        bytes(rng.randrange(256) for _ in range(2048)),
    ]
    for data in cases:
        _rt(data)


def test_nonregression_against_valid_legacy_floor():
    data = b"alpha,beta,gamma,delta\n" * 800
    v5_archive = _rt(data)
    valid = []
    for archive, _label in v5.v4_candidates(data):
        try:
            if v5.decompress(archive) == data:
                valid.append(archive)
        except Exception:
            pass
    assert valid
    assert len(v5_archive) <= min(map(len, valid))


def test_exact_zlib_semantic_stream_roundtrip():
    plain = b"BT /F1 12 Tf 72 720 Td (hello temporal world) Tj ET\n" * 100
    comp = zlib.compress(plain, 6)
    pdf = (
        b"%PDF-1.4\n1 0 obj\n<< /Length " + str(len(comp)).encode() +
        b" >>\nstream\n" + comp + b"\nendstream\nendobj\n%%EOF\n"
    )
    normalized = v5.normalize_zlib_streams(pdf)
    assert normalized is not None
    assert normalized[1] == 1
    _rt(pdf)


def test_sparse_legacy_route_is_exact():
    data = bytearray(8192)
    for i in range(0, len(data), 89):
        data[i] = (i * 17) % 255 + 1
    archive = _rt(bytes(data))
    assert v5.decompress(archive) == bytes(data)
