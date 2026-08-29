import hashlib

from qr_temporal import top10_x2_core as x2


def _samples():
    yield b"hello world 123 124 125\n" * 100
    yield bytes(range(256)) * 64
    yield bytes(16384)
    yield (
        b'{"t":1,"x":100.00000000,"s":"OK"}\n'
        b'{"t":2,"x":100.01000000,"s":"OK"}\n'
    ) * 200


def test_profiles_exact():
    for data in _samples():
        for fn in (
            x2.compress_max,
            x2.compress_whole,
            x2.compress_balanced,
            x2.compress_speed,
            x2.compress_turbo_score,
        ):
            archive = fn(data)
            restored = x2.decompress(archive)
            assert restored == data
            assert hashlib.sha256(restored).digest() == hashlib.sha256(data).digest()


def test_table_exact():
    data = b"".join(f"{i},{i % 7},{100 + i / 100:.2f},ok\n".encode() for i in range(1000))
    raw = x2.table_normalize(data)
    assert raw is not None
    assert x2.table_denormalize(raw) == data


def test_nonregression_floor():
    for data in _samples():
        archive = x2.compress_max(data)
        raw = x2._wrap(x2.base.RAW, data, data)
        assert len(archive) <= len(raw)
