from qr_temporal.qtd41 import Entry, Model
from qr_temporal import qtm_ar3 as ar3


def _fixture():
    old = (b"temporal compression graph predictor archive timestamp phrase model\n" * 20)
    new = old.replace(b"graph predictor", b"graph learned predictor") + (b"archive phrase temporal\n" * 8)
    model = Model.build([Entry("doc.txt", 1000, old)])
    return old, new, model


def test_qtm_ar3_byte_exact_and_max_nonregressing():
    _, target, model = _fixture()
    phrase = ar3.pack_phrase(target, "doc.txt", model, 2000)
    assert ar3.unpack_phrase(phrase, model) == target

    best = ar3.pack_max(target, "doc.txt", model, 2000)
    assert ar3.unpack_max(best, model) == target
    q41 = ar3.q41.pack(target, "doc.txt", model, 2000)
    a1 = ar3.ar1.pack_ar(target, "doc.txt", model, 2000, q41)
    a2 = ar3.ar2.pack_unified(target, "doc.txt", model, 2000, q41)
    assert len(best) <= min(len(q41), len(a1), len(a2), len(phrase))


def test_qtm_ar3_temporal_phrase_carrier_exact():
    _, target, model = _fixture()
    core, timestamps, info = ar3.pack_temporal(
        target, "doc.txt", model, 2000, m=256, k=1, min_phrase_len=2
    )
    assert timestamps[0] == 2000
    assert all(b > a for a, b in zip(timestamps, timestamps[1:]))
    assert info["events"] > 0
    assert info["covered"] > 0
    assert ar3.unpack_temporal(core, timestamps, model, m=256, k=1) == target


def test_qtm_ar3_phrase_lengths_are_temporal_model_state():
    old, _, model = _fixture()
    vocab = ar3.Vocabulary(model, "doc.txt", 2000)
    assert len(vocab) > 0
    assert all(2 <= len(p) <= 16 for p in vocab.p)


def test_qtm_ar3_rejects_target_leakage():
    _, target, _ = _fixture()
    leaked = Model.build([Entry("doc.txt", 1000, target)])
    try:
        ar3.pack_temporal(target, "doc.txt", leaked, 2000)
    except ValueError as exc:
        assert "leakage" in str(exc)
    else:
        raise AssertionError("target leakage was accepted")
