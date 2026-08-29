from qr_temporal.qtd41 import Entry, Model
from qr_temporal import qtm_ar3 as ar3


def test_qtm_ar3_variable_vocab_temporal_roundtrip():
    old=(b"temporal compression phrase graph model archive timestamp predictor\n"*32)
    target=old.replace(b"phrase graph",b"phrase learned graph")+(b"timestamp phrase archive\n"*12)
    model=Model.build([Entry("doc.txt",1000,old)])
    for vocab_size in (512,4096,16384):
        core, timestamps, info = ar3.pack_temporal(
            target,"doc.txt",model,2000,
            m=4096,k=1,min_phrase_len=2,vocab_size=vocab_size,
        )
        assert timestamps[0] == 2000
        assert all(b>a for a,b in zip(timestamps,timestamps[1:]))
        assert info["events"] > 0
        assert info["covered"] > 0
        assert ar3.unpack_temporal(core,timestamps,model,m=4096,k=1) == target


def test_qtm_ar3_rejects_unknown_vocab_profile():
    old=b"abc temporal phrase "*64
    target=old+b"future"
    model=Model.build([Entry("doc.txt",1000,old)])
    try:
        ar3.pack_temporal(target,"doc.txt",model,2000,vocab_size=777)
    except ValueError as exc:
        assert "vocab" in str(exc)
    else:
        raise AssertionError("unsupported vocab size accepted")
