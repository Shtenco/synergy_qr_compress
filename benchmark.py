from __future__ import annotations
import argparse, hashlib, json, os, time
from pathlib import Path
from qr_temporal import pack, unpack, inspect

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("input", nargs="?"); ap.add_argument("--random-bytes", type=int, default=0); args = ap.parse_args()
    if args.input: data = Path(args.input).read_bytes()
    elif args.random_bytes: data = os.urandom(args.random_bytes)
    else: data = b"temporal-qr-benchmark\n" * 10000
    t0=time.perf_counter(); packed=pack(data); t1=time.perf_counter(); restored=unpack(packed.blob); t2=time.perf_counter(); assert restored == data
    result=inspect(packed.blob); result.update({"encode_ms":(t1-t0)*1000,"decode_ms":(t2-t1)*1000,"byte_equal":restored==data,"sha256_equal":hashlib.sha256(restored).digest()==hashlib.sha256(data).digest()}); print(json.dumps(result, indent=2))

if __name__ == "__main__": main()
