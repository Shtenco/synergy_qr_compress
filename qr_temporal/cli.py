from __future__ import annotations
import argparse, json
from pathlib import Path
from .container import pack, unpack, inspect
from .qr import write_qr_sequence

def main() -> None:
    p = argparse.ArgumentParser(prog="qr-compress"); sub = p.add_subparsers(dest="cmd", required=True)
    enc = sub.add_parser("encode"); enc.add_argument("input"); enc.add_argument("-o", "--output", required=True); enc.add_argument("--qr-dir")
    dec = sub.add_parser("decode"); dec.add_argument("input"); dec.add_argument("-o", "--output", required=True)
    inf = sub.add_parser("inspect"); inf.add_argument("input"); args = p.parse_args()
    if args.cmd == "encode":
        data = Path(args.input).read_bytes(); packed = pack(data); Path(args.output).write_bytes(packed.blob)
        if args.qr_dir:
            paths = write_qr_sequence(packed.blob, packed.unix_ns, args.qr_dir); print(f"QR frames: {len(paths)}")
        print(json.dumps(inspect(packed.blob), indent=2))
    elif args.cmd == "decode": Path(args.output).write_bytes(unpack(Path(args.input).read_bytes()))
    else: print(json.dumps(inspect(Path(args.input).read_bytes()), indent=2))

if __name__ == "__main__": main()
