import os
import pytest
from qr_temporal import TemporalSample, TemporalDictionary, train_temporal_dictionary, pack_v2, unpack_v2, inspect_v2

BASE_TS = 1787990000000000000

def make_model(data: bytes):
    return train_temporal_dictionary([TemporalSample(BASE_TS, data)])

def test_model_serialization_deterministic_and_exact():
    data = b'{"type":"trade","symbol":"ETHUSDC","price":4500}' * 20
    model = make_model(data)
    blob = model.to_bytes()
    restored = TemporalDictionary.from_bytes(blob)
    assert restored.model_id == model.model_id
    assert restored.to_bytes() == blob
    assert restored.entries[0].data == data

def test_qtc2_exact_timestamp_address_roundtrip():
    data = os.urandom(4096)
    model = make_model(data)
    p = pack_v2(data, model=model)
    info = inspect_v2(p.blob, model)
    assert info["mode"] == "exact"
    assert info["payload_size"] == 0
    assert info["model_coverage_percent"] == 100.0
    assert info["target_99_9999_percent_met"] is True
    assert unpack_v2(p.blob, model) == data

def test_qtc2_patch_one_byte_reaches_999999_on_million_bytes():
    base = bytearray(os.urandom(1_000_000))
    model = make_model(bytes(base))
    target = bytearray(base)
    target[500_000] ^= 0x5A
    p = pack_v2(bytes(target), model=model)
    info = inspect_v2(p.blob, model)
    assert info["mode"] == "patch"
    assert info["covered_size"] >= 999_999
    assert info["model_coverage_percent"] >= 99.9999
    assert info["target_99_9999_percent_met"] is True
    assert unpack_v2(p.blob, model) == bytes(target)

def test_qtc2_wrong_model_rejected():
    model = make_model(b"alpha" * 100)
    wrong = make_model(b"beta" * 100)
    p = pack_v2(b"alpha" * 100, model=model)
    with pytest.raises(ValueError, match="model_id mismatch"):
        unpack_v2(p.blob, wrong)

def test_qtc2_corruption_rejected():
    base = b"hello world" * 1000
    model = make_model(base)
    target = base[:-1] + b"!"
    p = pack_v2(target, model=model)
    b = bytearray(p.blob)
    b[-1] ^= 1
    with pytest.raises(ValueError):
        unpack_v2(bytes(b), model)

def test_qtc2_falls_back_for_unrelated_data():
    model = make_model(b"A" * 10000)
    target = os.urandom(10000)
    p = pack_v2(target, model=model)
    assert unpack_v2(p.blob, model) == target
