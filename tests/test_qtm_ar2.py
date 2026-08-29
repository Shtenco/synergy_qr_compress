from qr_temporal.qtd41 import Entry, Model
from qr_temporal import qtm_ar as ar1
from qr_temporal import qtm_ar2 as ar2


def test_qtm_ar2_exact_and_nonregressing():
    old = b"header\nalpha beta gamma\nfooter\n" * 12
    new = old.replace(b"gamma", b"gamma-v2") + b"new section\n" * 4
    model = Model.build([Entry("doc.txt", 1000, old)])
    a2 = ar2.pack_ar2(new, "doc.txt", model, 2000)
    assert ar2.unpack_ar2(a2, model) == new
    au = ar2.pack_unified(new, "doc.txt", model, 2000)
    assert ar2.unpack_unified(au, model) == new

    best = ar2.pack_max(new, "doc.txt", model, 2000)
    assert ar2.unpack_max(best, model) == new

    q41 = ar2.q41.pack(new, "doc.txt", model, 2000)
    a1 = ar1.pack_ar(new, "doc.txt", model, 2000, q41)
    assert len(best) <= min(len(q41), len(a1), len(a2), len(au))


def test_qtm_ar2_cross_file_exact():
    model = Model.build([
        Entry("test_a.py", 100, b"import os\n\ndef test_a():\n    source=b'ABC'*100\n    assert source\n"),
        Entry("test_b.py", 110, b"import hashlib\n\ndef test_b():\n    source=b'XYZ'*100\n    assert source\n"),
    ])
    target = b"import os\n\ndef test_c():\n    source=b'ABC'*50\n    assert source\n"
    blob = ar2.pack_ar2(target, "test_c.py", model, 200)
    assert ar2.unpack_ar2(blob, model) == target


def test_temporal_combination_roundtrip():
    source = bytes(range(256)) * 2
    for m, k in ((256, 32), (2048, 48), (16384, 12), (65536, 8)):
        ts = ar2.temporal_encode(source, m=m, k=k)
        assert all(b > a for a, b in zip(ts, ts[1:]))
        assert ar2.temporal_decode(ts, m=m, k=k) == source


def test_combinadic_bijection():
    for m, k in ((64, 4), (256, 8), (4096, 12)):
        limit = min(1000, 1 << (ar2.math.comb(m, k).bit_length() - 1))
        for rank in range(0, limit, max(1, limit // 37)):
            combo = ar2.comb_unrank(rank, k, m)
            assert ar2.comb_rank(combo) == rank
