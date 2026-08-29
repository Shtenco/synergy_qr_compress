from __future__ import annotations
import argparse
import json
from pathlib import Path
from .container import pack, unpack, inspect
from .model import TemporalDictionary, TemporalSample, samples_from_paths, train_temporal_dictionary
from .qtc2 import pack_v2, unpack_v2, inspect_v2
from .qr import write_qr_sequence

def _expand_inputs(values: list[str], recursive: bool) -> list[Path]:
    out: list[Path] = []
    for raw in values:
        p = Path(raw)
        if p.is_file():
            out.append(p)
        elif p.is_dir():
            out.extend(x for x in (p.rglob("*") if recursive else p.glob("*")) if x.is_file())
        else:
            raise FileNotFoundError(raw)
    return sorted(set(out))

def _load_manifest(path: str | None) -> list[TemporalSample]:
    if not path:
        return []
    root = Path(path).resolve().parent
    samples: list[TemporalSample] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        p = Path(row["path"])
        if not p.is_absolute():
            p = root / p
        samples.append(TemporalSample(int(row["unix_ns"]), p.read_bytes()))
    return samples

def main() -> None:
    p = argparse.ArgumentParser(prog="qr-compress")
    sub = p.add_subparsers(dest="cmd", required=True)

    enc = sub.add_parser("encode", help="QTC1 standalone encode")
    enc.add_argument("input")
    enc.add_argument("-o", "--output", required=True)
    enc.add_argument("--qr-dir")
    enc.add_argument("--unix-ns", type=int)

    dec = sub.add_parser("decode", help="QTC1 standalone decode")
    dec.add_argument("input")
    dec.add_argument("-o", "--output", required=True)

    inf = sub.add_parser("inspect", help="inspect QTC1")
    inf.add_argument("input")

    train = sub.add_parser("train-model", help="build QTD1 temporal model")
    train.add_argument("inputs", nargs="*")
    train.add_argument("-o", "--output", required=True)
    train.add_argument("--recursive", action="store_true")
    train.add_argument("--manifest", help="JSONL rows: {path, unix_ns}")

    enc2 = sub.add_parser("encode2", help="QTC2 temporal-model encode")
    enc2.add_argument("input")
    enc2.add_argument("-o", "--output", required=True)
    enc2.add_argument("--model")
    enc2.add_argument("--qr-dir")
    enc2.add_argument("--unix-ns", type=int)
    enc2.add_argument("--candidate-limit", type=int, default=8)

    dec2 = sub.add_parser("decode2", help="QTC2 temporal-model decode")
    dec2.add_argument("input")
    dec2.add_argument("-o", "--output", required=True)
    dec2.add_argument("--model")

    inf2 = sub.add_parser("inspect2", help="inspect QTC2")
    inf2.add_argument("input")
    inf2.add_argument("--model")

    args = p.parse_args()

    if args.cmd == "encode":
        data = Path(args.input).read_bytes()
        packed = pack(data, unix_ns=args.unix_ns)
        Path(args.output).write_bytes(packed.blob)
        if args.qr_dir:
            paths = write_qr_sequence(packed.blob, packed.unix_ns, args.qr_dir)
            print(f"QR frames: {len(paths)}")
        print(json.dumps(inspect(packed.blob), indent=2))
    elif args.cmd == "decode":
        Path(args.output).write_bytes(unpack(Path(args.input).read_bytes()))
    elif args.cmd == "inspect":
        print(json.dumps(inspect(Path(args.input).read_bytes()), indent=2))
    elif args.cmd == "train-model":
        samples = _load_manifest(args.manifest)
        if args.inputs:
            files = _expand_inputs(args.inputs, args.recursive)
            samples.extend(samples_from_paths(files))
        model = train_temporal_dictionary(samples)
        model.save(args.output)
        print(json.dumps({
            "magic": "QTD1",
            "entries": len(model.entries),
            "model_bytes": len(model.to_bytes()),
            "model_id": model.model_id.hex(),
            "output": str(Path(args.output)),
        }, indent=2))
    elif args.cmd == "encode2":
        data = Path(args.input).read_bytes()
        model = TemporalDictionary.load(args.model) if args.model else None
        packed = pack_v2(data, model=model, unix_ns=args.unix_ns, candidate_limit=args.candidate_limit)
        Path(args.output).write_bytes(packed.blob)
        if args.qr_dir:
            paths = write_qr_sequence(packed.blob, packed.unix_ns, args.qr_dir)
            print(f"QR frames: {len(paths)}")
        print(json.dumps(inspect_v2(packed.blob, model), indent=2))
    elif args.cmd == "decode2":
        model = TemporalDictionary.load(args.model) if args.model else None
        Path(args.output).write_bytes(unpack_v2(Path(args.input).read_bytes(), model=model))
    elif args.cmd == "inspect2":
        model = TemporalDictionary.load(args.model) if args.model else None
        print(json.dumps(inspect_v2(Path(args.input).read_bytes(), model=model), indent=2))

if __name__ == "__main__":
    main()
