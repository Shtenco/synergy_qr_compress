import hashlib
import pytest

from qr_temporal.qtd41 import Entry, Model, pack, unpack, inspect


def test_qtd41_lineage_exact_and_context_predictor():
    old = b"header\nalpha beta gamma\nfooter\n" * 20
    target = old.replace(b"gamma", b"gamma-v2") + b"new section\n" * 10
    model = Model.build([Entry("doc.txt", 1000, old)])
    blob = pack(target, "doc.txt", model, 2000)
    assert unpack(blob, model) == target
    info = inspect(blob, model)
    assert info["model_match"] is True
    assert hashlib.sha256(unpack(blob, model)).digest() == hashlib.sha256(target).digest()


def test_qtd41_cross_file_copy_graph_exact():
    model = Model.build([
        Entry("test_a.py", 100, b"import os\n\ndef test_a():\n    source=b'ABC'*100\n    assert source\n"),
        Entry("test_b.py", 110, b"import hashlib\n\ndef test_b():\n    source=b'XYZ'*100\n    assert source\n"),
    ])
    target = b"import os\n\ndef test_c():\n    source=b'ABC'*50\n    assert source\n"
    blob = pack(target, "test_c.py", model, 200)
    assert unpack(blob, model) == target
    assert inspect(blob, model)["covered_bytes"] > 0


def test_qtd41_rejects_target_and_temporal_leakage():
    target = b"already known"
    model = Model.build([Entry("x.bin", 100, target)])
    with pytest.raises(ValueError, match="leakage"):
        pack(target, "x.bin", model, 200)
    model2 = Model.build([Entry("x.bin", 300, b"past?")])
    with pytest.raises(ValueError, match="leakage"):
        pack(b"future", "y.bin", model2, 300)


def test_qtd41_wrong_model_rejected():
    model = Model.build([Entry("a.py", 100, b"def alpha():\n    return 1\n")])
    target = b"def beta():\n    return 1\n"
    blob = pack(target, "b.py", model, 200)
    wrong = Model.build([Entry("a.py", 100, b"different data")])
    with pytest.raises(ValueError):
        unpack(blob, wrong)
