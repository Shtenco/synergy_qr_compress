#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math, pickle, time
from pathlib import Path
import brotli

from qr_temporal import fusion_v5_x2 as v5

DEFAULT_CASES = [
    "source_code_8k", "json_graph_logs_8k", "structured_binary_8k", "image_like_8k",
    "version_snapshots_8k", "repeated_text_8k", "sparse_weights_8k", "bip39_text_8k",
    "real_png64", "real_pdf64", "real_jpg64", "random_8k",
]


def gm(values):
    return math.exp(sum(math.log(max(float(x), 1e-15)) for x in values) / len(values))


def valid_legacy_floor(data: bytes) -> bytes:
    valid = []
    for archive, label in v5.v4_candidates(data):
        try:
            if v5.decompress(archive) == data:
                valid.append((archive, label))
        except Exception:
            pass
    if not valid:
        raise RuntimeError("no exact legacy candidate")
    return min(valid, key=lambda x: (len(x[0]), x[1]))[0]


def run(corpus_path: Path, cases: list[str]):
    corpus = pickle.loads(corpus_path.read_bytes())
    rows = []
    for name in cases:
        data = corpus[name]
        legacy = valid_legacy_floor(data)
        t = time.perf_counter()
        archive = v5.compress(data)
        encode_ms = (time.perf_counter() - t) * 1000
        restored = v5.decompress(archive)
        assert restored == data
        assert hashlib.sha256(restored).digest() == hashlib.sha256(data).digest()
        br = brotli.compress(data, quality=11)
        rows.append({
            "dataset": name,
            "source_bytes": len(data),
            "legacy_v4_bytes": len(legacy),
            "v5_bytes": len(archive),
            "brotli11_bytes": len(br),
            "legacy_v4_ratio": len(data) / len(legacy),
            "v5_ratio": len(data) / len(archive),
            "gain_vs_v4_percent": 100.0 * (len(legacy) - len(archive)) / len(legacy),
            "encode_ms": encode_ms,
            "selected": v5.inspect(archive),
            "status": "PASS",
        })
    summary = {
        "cases": len(rows),
        "geomean_v4_ratio": gm([r["legacy_v4_ratio"] for r in rows]),
        "geomean_v5_ratio": gm([r["v5_ratio"] for r in rows]),
    }
    summary["relative_ratio_gain"] = summary["geomean_v5_ratio"] / summary["geomean_v4_ratio"]
    return {"summary": summary, "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--output", type=Path, default=Path("fusion_v5_x2_benchmark.json"))
    ap.add_argument("--cases", nargs="*", default=DEFAULT_CASES)
    args = ap.parse_args()
    result = run(args.corpus, args.cases)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))

if __name__ == "__main__":
    main()
