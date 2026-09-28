from qr_temporal.qtd3 import RepoBlob
from qr_temporal.synergy_contracts import CONTRACT_ID, lossless_benchmark_payload

def test_lossless_benchmark_is_exact_and_non_deploying():
    blobs=[
        RepoBlob("a.txt",1,b"hello world\n"*10),
        RepoBlob("b.txt",2,b"hello there\n"*10),
    ]
    target=b"hello world\n"*9+b"new line\n"
    p=lossless_benchmark_payload(
        benchmark_id="q1",training_blobs=blobs,target=target,path="a.txt",target_unix_ns=3
    )
    assert CONTRACT_ID=="synergy.archive.benchmark-evidence/v1"
    assert p["round_trip_verified"] is True
    assert p["temporal_cutoff_valid"] is True
    assert p["deployment_authority"] is False
