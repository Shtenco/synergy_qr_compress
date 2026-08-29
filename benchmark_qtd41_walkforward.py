#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from benchmark_qtd3_walkforward import (
    DEFAULT_CASES,
    _baselines,
    _blob,
    _commit_unix_ns,
    build_repository_model,
)
from qr_temporal.qtd3 import pack_blind_v3, unpack_v3, inspect_v3
from qr_temporal.qtd41 import Entry, Model, pack as pack41, unpack as unpack41, inspect as inspect41


def adapt_model(qtd3_model):
    return Model(
        tuple(Entry(e.path, e.unix_ns, e.data) for e in qtd3_model.entries),
        qtd3_model.model_id,
    )


def run_case(repo: Path, case: dict, history_depth: int, max_file_bytes: int) -> dict:
    model3, meta = build_repository_model(
        repo, case["base"], history_depth=history_depth, max_file_bytes=max_file_bytes
    )
    model41 = adapt_model(model3)
    target = _blob(repo, case["target"], case["path"])
    target_ns = _commit_unix_ns(repo, case["target"])
    target_sha = hashlib.sha256(target).digest()
    if target_sha in model3.leakage_guard:
        raise RuntimeError(f"target leakage: {case['name']}")
    if model3.max_unix_ns >= target_ns:
        raise RuntimeError(f"temporal leakage: {case['name']}")

    p3 = pack_blind_v3(target, case["path"], model3, unix_ns=target_ns)
    r3 = unpack_v3(p3.blob, model3)
    p41 = pack41(target, case["path"], model41, target_ns)
    r41 = unpack41(p41, model41)
    if r3 != target or r41 != target:
        raise RuntimeError(f"byte equality failed: {case['name']}")

    i3 = inspect_v3(p3.blob, model3)
    i41 = inspect41(p41, model41)
    bases = _baselines(target)
    direct_name, direct_bytes = min(bases.items(), key=lambda x:(x[1],x[0]))
    model_bytes = len(model3.to_bytes())
    return {
        "name": case["name"],
        "base_commit": case["base"],
        "target_commit": case["target"],
        "path": case["path"],
        "target_bytes": len(target),
        "target_sha256": target_sha.hex(),
        "target_sha_absent_from_training": True,
        "temporal_cutoff_valid": True,
        "byte_equal_qtd3": r3 == target,
        "byte_equal_qtd41": r41 == target,
        "sha256_equal_qtd41": hashlib.sha256(r41).digest() == target_sha,
        "shared_model_bytes": model_bytes,
        "model_entries": len(model3.entries),
        "qtd3": i3,
        "qtd41": i41,
        "direct_baselines_bytes": bases,
        "direct_best_codec": direct_name,
        "direct_best_bytes": direct_bytes,
        "qtd41_vs_qtd3_reduction_percent": 100.0 * (1.0 - len(p41) / len(p3.blob)),
        "qtd41_vs_direct_best_reduction_percent": 100.0 * (1.0 - len(p41) / direct_bytes),
        "cold_qtd3_bytes": model_bytes + len(p3.blob),
        "cold_qtd41_bytes": model_bytes + len(p41),
        "model_meta": meta,
    }


def main():
    ap = argparse.ArgumentParser(description="QTD4.1 vs QTD3 strict real-Git walk-forward")
    ap.add_argument("repo", type=Path)
    ap.add_argument("--cases-json", type=Path)
    ap.add_argument("--history-depth", type=int, default=2)
    ap.add_argument("--max-file-bytes", type=int, default=262_144)
    ap.add_argument("-o", "--output", type=Path)
    a = ap.parse_args()
    cases = DEFAULT_CASES if not a.cases_json else json.loads(a.cases_json.read_text(encoding="utf-8"))
    rows = [run_case(a.repo.resolve(), c, a.history_depth, a.max_file_bytes) for c in cases]
    source = sum(r["target_bytes"] for r in rows)
    q3 = sum(r["qtd3"]["container_size"] for r in rows)
    q41 = sum(r["qtd41"]["container_size"] for r in rows)
    direct = sum(r["direct_best_bytes"] for r in rows)
    covered = sum(r["qtd41"]["covered_bytes"] for r in rows)
    report = {
        "method": "Fusion V4.1 / QTD4.1 strict side-by-side real Git walk-forward",
        "history_depth": a.history_depth,
        "max_file_bytes": a.max_file_bytes,
        "cases": rows,
        "aggregate": {
            "target_count": len(rows),
            "source_bytes": source,
            "qtd3_container_bytes": q3,
            "qtd41_container_bytes": q41,
            "direct_best_bytes": direct,
            "qtd3_ratio": source / q3 if q3 else 0,
            "qtd41_ratio": source / q41 if q41 else 0,
            "qtd41_vs_qtd3_reduction_percent": 100.0 * (1.0 - q41 / q3) if q3 else 0,
            "qtd41_vs_direct_best_reduction_percent": 100.0 * (1.0 - q41 / direct) if direct else 0,
            "weighted_copy_coverage_percent": 100.0 * covered / source if source else 100.0,
            "all_byte_equal": all(r["byte_equal_qtd3"] and r["byte_equal_qtd41"] for r in rows),
            "all_sha256_equal": all(r["sha256_equal_qtd41"] for r in rows),
            "all_target_sha_absent_from_training": all(r["target_sha_absent_from_training"] for r in rows),
            "all_temporal_cutoff_valid": all(r["temporal_cutoff_valid"] for r in rows),
        },
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
