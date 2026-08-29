from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import bz2
import lzma
import zlib

from qr_temporal.qtd2 import HistoricalSnapshot, train_qtd2, pack_blind, unpack_blind, inspect_blind

PROFILES = ((4,8,16), (6,12,24), (8,16,32), (16,32,64), (20,40,80), (24,48,96), (32,64,128), (48,96,192), (64,128,256))


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def direct_baselines(data: bytes) -> dict[str, int]:
    out = {
        "raw": len(data),
        "zlib9": len(zlib.compress(data, 9)),
        "bz2_9": len(bz2.compress(data, 9)),
        "lzma_extreme": len(lzma.compress(data, preset=9 | lzma.PRESET_EXTREME)),
    }
    try:
        import brotli
        out["brotli11"] = len(brotli.compress(data, quality=11, mode=brotli.MODE_GENERIC))
    except Exception:
        pass
    try:
        import zstandard as zstd
        out["zstd19"] = len(zstd.ZstdCompressor(level=19, write_checksum=True, write_content_size=True).compress(data))
    except Exception:
        pass
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Blind QTD2 benchmark over real Git history snapshots")
    ap.add_argument("--train", action="append", required=True, help="unix_ns:path:expected_git_blob_sha")
    ap.add_argument("--target", required=True, help="unix_ns:path:expected_git_blob_sha")
    ap.add_argument("-o", "--output", type=Path)
    args = ap.parse_args()

    snapshots = []
    train_meta = []
    for spec in args.train:
        ns_s, path_s, sha = spec.split(":", 2)
        data = Path(path_s).read_bytes()
        actual = git_blob_sha1(data)
        if actual != sha.lower():
            raise SystemExit(f"training Git blob mismatch for {path_s}: expected {sha}, got {actual}")
        snapshots.append(HistoricalSnapshot(int(ns_s), data))
        train_meta.append({"path": path_s, "unix_ns": int(ns_s), "bytes": len(data), "git_blob_sha1": actual, "sha256": hashlib.sha256(data).hexdigest()})

    tns_s, tpath_s, tsha = args.target.split(":", 2)
    target = Path(tpath_s).read_bytes()
    actual_target_git = git_blob_sha1(target)
    if actual_target_git != tsha.lower():
        raise SystemExit(f"target Git blob mismatch: expected {tsha}, got {actual_target_git}")
    target_sha256 = hashlib.sha256(target).digest()

    rows = []
    for mn, av, mx in PROFILES:
        model = train_qtd2(snapshots, min_size=mn, avg_size=av, max_size=mx)
        if target_sha256 in model.target_leakage_guard:
            raise AssertionError("target leakage into training model")
        packed = pack_blind(target, model, unix_ns=int(tns_s))
        restored = unpack_blind(packed.blob, model)
        if restored != target or hashlib.sha256(restored).digest() != target_sha256:
            raise AssertionError("QTD2 exact round-trip failed")
        meta = inspect_blind(packed.blob, model)
        rows.append({
            "profile": [mn,av,mx],
            "model_bytes": len(model.to_bytes()),
            "model_chunks": len(model.chunks),
            "ref_count": packed.ref_count,
            "literal_bytes": packed.literal_bytes,
            **meta,
        })

    best = min(rows, key=lambda r: (r["container_size"], -r["model_coverage_percent"]))
    baselines = direct_baselines(target)
    cold_total = best["model_bytes"] + best["container_size"]
    result = {
        "method": "QTD2 blind Git-history benchmark",
        "training": train_meta,
        "target": {
            "path": tpath_s,
            "unix_ns": int(tns_s),
            "bytes": len(target),
            "git_blob_sha1": actual_target_git,
            "sha256": target_sha256.hex(),
            "sha256_absent_from_training": True,
        },
        "profiles": rows,
        "best": best,
        "direct_baselines_bytes": baselines,
        "best_vs_direct_brotli_reduction_percent": None if "brotli11" not in baselines else 100.0 * (1.0 - best["container_size"] / baselines["brotli11"]),
        "cold_total_bytes_model_plus_first_target": cold_total,
        "cold_reduction_percent": 100.0 * (1.0 - cold_total / len(target)),
        "amortized_targets_to_beat_raw": max(1, (best["model_bytes"] + (len(target)-best["container_size"])-1) // (len(target)-best["container_size"])),
        "amortized_targets_to_beat_direct_brotli": None if "brotli11" not in baselines or baselines["brotli11"] <= best["container_size"] else max(1, (best["model_bytes"] + (baselines["brotli11"]-best["container_size"])-1) // (baselines["brotli11"]-best["container_size"])),
        "shared_brotli_rfc9841_used": False,
        "notes": [
            "Target full SHA-256 is explicitly absent from training manifest.",
            "Brotli candidate operates on the chunk-reference residual stream; this runtime does not expose RFC 9841 Shared Brotli dictionary APIs.",
            "Zstandard trained-dictionary and Gabriel-Horn routes are attempted when their Python modules are available.",
        ],
    }
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)

if __name__ == "__main__":
    main()
