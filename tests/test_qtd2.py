import hashlib
import pytest

from qr_temporal.qtd2 import HistoricalSnapshot, train_qtd2, pack_blind, unpack_blind, fastcdc


def test_fastcdc_is_deterministic_and_complete():
    data = (b"abcde" * 1000) + b"tail"
    a = fastcdc(data, 16, 32, 64)
    b = fastcdc(data, 16, 32, 64)
    assert a == b
    assert b"".join(a) == data


def test_blind_target_not_in_training_roundtrip():
    v1 = b"header\nalpha\nbeta\ntail\n" * 30
    v2 = b"header\nalpha\nbeta\ngamma\ntail\n" * 30
    target = b"header\nalpha\nbeta\ngamma\nNEW-BLOCK\ntail\n" * 30
    model = train_qtd2([
        HistoricalSnapshot(1_000_000_000, v1),
        HistoricalSnapshot(2_000_000_000, v2),
    ], min_size=8, avg_size=16, max_size=32)
    assert hashlib.sha256(target).digest() not in model.target_leakage_guard
    packed = pack_blind(target, model, unix_ns=3_000_000_000)
    assert unpack_blind(packed.blob, model) == target
    assert packed.covered_bytes > 0
    assert packed.literal_bytes > 0


def test_blind_guard_rejects_seen_target():
    target = b"already-known"
    model = train_qtd2([HistoricalSnapshot(1_000_000_000, target)])
    with pytest.raises(ValueError, match="blind benchmark violation"):
        pack_blind(target, model)


def test_wrong_model_rejected():
    target = b"alpha beta gamma delta" * 20
    model_a = train_qtd2([HistoricalSnapshot(1_000_000_000, b"alpha beta gamma" * 20)], min_size=8, avg_size=16, max_size=32)
    model_b = train_qtd2([HistoricalSnapshot(1_000_000_000, b"other corpus" * 20)], min_size=8, avg_size=16, max_size=32)
    packed = pack_blind(target, model_a, unix_ns=2_000_000_000)
    with pytest.raises(ValueError, match="model_id mismatch"):
        unpack_blind(packed.blob, model_b)
