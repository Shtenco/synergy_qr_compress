import os
from qr_temporal import pack, unpack, split_frames, join_frames

def test_roundtrip_text():
    data = ("temporal compression " * 500).encode(); p = pack(data, unix_ns=1787990000000000000); assert unpack(p.blob) == data

def test_roundtrip_random():
    data = os.urandom(8192); p = pack(data, unix_ns=1787990000000000000); assert unpack(p.blob) == data

def test_frames_reorder():
    data = b"ABCDEFGH" * 2000; p = pack(data, unix_ns=1787990000000000000); frames = split_frames(p.blob, p.unix_ns, max_frame_bytes=400); ts, blob = join_frames([x.bytes for x in reversed(frames)]); assert ts == p.unix_ns; assert unpack(blob) == data

def test_corruption_rejected():
    data = b"hello" * 100; p = pack(data, unix_ns=1787990000000000000); b = bytearray(p.blob); b[-1] ^= 1
    try: unpack(bytes(b))
    except ValueError: pass
    else: raise AssertionError("corruption was not rejected")
