import os
from qr_temporal.rans import compress, decompress

def test_rans_roundtrip():
    cases = [b"", b"a", b"ab"*1000, b"hello world"*1000, os.urandom(5000)]
    for data in cases:
        assert decompress(compress(data)) == data
