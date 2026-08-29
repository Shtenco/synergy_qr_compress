import hashlib
import pytest

from qr_temporal.qtd3 import RepoBlob, train_qtd3, pack_blind_v3, unpack_v3, inspect_v3

def test_qtd3_model_roundtrip_and_blind_exact():
    old = b"header\nalpha beta gamma\nfooter\n" * 20
    newer = old.replace(b"gamma", b"gamma-v2") + b"new section\n" * 10
    model = train_qtd3([RepoBlob("doc.txt", 1_000, old)])
    loaded = type(model).from_bytes(model.to_bytes())
    packed = pack_blind_v3(newer, "doc.txt", loaded, unix_ns=2_000)
    assert unpack_v3(packed.blob, loaded) == newer
    info = inspect_v3(packed.blob, loaded)
    assert info["model_match"] is True
    assert info["temporal_cutoff_valid"] is True
    assert info["covered_bytes"] > 0

def test_qtd3_rejects_target_leakage():
    target = b"already known"
    model = train_qtd3([RepoBlob("x.bin", 100, target)])
    with pytest.raises(ValueError, match="target SHA-256"):
        pack_blind_v3(target, "x.bin", model, unix_ns=200)

def test_qtd3_rejects_temporal_leakage():
    model = train_qtd3([RepoBlob("x.bin", 300, b"past?")])
    with pytest.raises(ValueError, match="temporal leakage"):
        pack_blind_v3(b"future", "y.bin", model, unix_ns=300)

def test_qtd3_wrong_model_and_corruption_rejected():
    model = train_qtd3([RepoBlob("a.py", 100, b"def alpha():\n    return 1\n")])
    target = b"def beta():\n    return 1\n"
    packed = pack_blind_v3(target, "b.py", model, unix_ns=200)
    wrong = train_qtd3([RepoBlob("a.py", 100, b"different data")])
    with pytest.raises(ValueError, match="model fingerprint"):
        unpack_v3(packed.blob, wrong)
    damaged = bytearray(packed.blob)
    damaged[-1] ^= 1
    with pytest.raises(Exception):
        unpack_v3(bytes(damaged), model)

def test_qtd3_cross_file_prediction():
    training = [
        RepoBlob("test_a.py", 100, b"import os\n\ndef test_a():\n    source=b'ABC'*100\n    assert source\n"),
        RepoBlob("test_b.py", 110, b"import hashlib\n\ndef test_b():\n    source=b'XYZ'*100\n    assert source\n"),
    ]
    target = b"import os\n\ndef test_c():\n    source=b'ABC'*50\n    assert source\n"
    model = train_qtd3(training)
    packed = pack_blind_v3(target, "test_c.py", model, unix_ns=200)
    assert unpack_v3(packed.blob, model) == target
    assert packed.covered_bytes > 0
