#!/usr/bin/env python3
from __future__ import annotations

import argparse
import bz2
import hashlib
import json
import lzma
from pathlib import Path
import subprocess
import zlib

from qr_temporal.qtd3 import (
    RepoBlob,
    train_qtd3,
    pack_blind_v3,
    unpack_v3,
    inspect_v3,
)

DEFAULT_CASES = [
    {
        "name": "readme-evolution",
        "base": "9832a2d424b8500bfcc01e088f6119f1419a09bb",
        "target": "79915e036d80f98be9e72aa6dbd6b37a8d135f45",
        "path": "README.md",
    },
    {
        "name": "new-tier1-v2-test",
        "base": "0125f04cdaa350986c123b1208cd9623c372e886",
        "target": "983d1c526c87e330f5cfca024dbfabda0c23dae4",
        "path": "compression_lab/test_tier1_v2.py",
    },
    {
        "name": "new-unified-workflow",
        "base": "983d1c526c87e330f5cfca024dbfabda0c23dae4",
        "target": "3af005515e0148cd729a39e86b40dab0877157d5",
        "path": ".github/workflows/unified_tier1_v2_benchmark.yml",
    },
]

TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".json", ".csv", ".yml", ".yaml", ".toml",
    ".ini", ".cfg", ".sh", ".bat", ".ps1", ".gitmodules",
}


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), *args])


def _commit_unix_ns(repo: Path, commit: str) -> int:
    return int(_git(repo, "show", "-s", "--format=%ct", commit).strip()) * 1_000_000_000


def _blob(repo: Path, commit: str, path: str) -> bytes:
    return _git(repo, "show", f"{commit}:{path}")


def _git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def _eligible(path: str, size: int, max_bytes: int) -> bool:
    if size < 0 or size > max_bytes:
        return False
    p = Path(path)
    if p.name == ".gitmodules":
        return True
    return p.suffix.lower() in TEXT_SUFFIXES


def _tree(repo: Path, commit: str, max_bytes: int) -> list[tuple[str, int]]:
    raw = _git(repo, "ls-tree", "-r", "-l", commit).decode("utf-8", errors="strict")
    rows = []
    for line in raw.splitlines():
        meta, path = line.split("\t", 1)
        parts = meta.split()
        if len(parts) != 4 or parts[1] != "blob":
            continue
        try:
            size = int(parts[3])
        except ValueError:
            continue
        if _eligible(path, size, max_bytes):
            rows.append((path, size))
    return rows


def _path_history(repo: Path, base: str, path: str, depth: int) -> list[str]:
    raw = _git(repo, "log", f"-n{depth}", "--format=%H", base, "--", path)
    return [line for line in raw.decode().splitlines() if line]


def build_repository_model(
    repo: Path,
    base: str,
    *,
    history_depth: int = 2,
    max_file_bytes: int = 262_144,
) -> tuple[object, dict]:
    blobs: list[RepoBlob] = []
    seen: set[tuple[str, bytes]] = set()
    listed = _tree(repo, base, max_file_bytes)
    for path, _ in listed:
        commits = _path_history(repo, base, path, max(1, history_depth))
        if not commits:
            commits = [base]
        for commit in commits:
            try:
                data = _blob(repo, commit, path)
            except subprocess.CalledProcessError:
                continue
            digest = hashlib.sha256(data).digest()
            key = (path, digest)
            if key in seen:
                continue
            seen.add(key)
            blobs.append(RepoBlob(path, _commit_unix_ns(repo, commit), data))
    model = train_qtd3(blobs)
    meta = {
        "base_commit": base,
        "eligible_paths": len(listed),
        "training_blob_versions": len(blobs),
        "training_raw_bytes": sum(len(b.data) for b in blobs),
        "model_serialized_bytes": len(model.to_bytes()),
        "model_sha256": model.model_id.hex(),
        "max_training_unix_ns": model.max_unix_ns,
        "history_depth": history_depth,
        "max_file_bytes": max_file_bytes,
    }
    return model, meta


def _baselines(data: bytes) -> dict[str, int]:
    values = {
        "raw": len(data),
        "zlib9": len(zlib.compress(data, 9)),
        "bz2_9": len(bz2.compress(data, 9)),
        "lzma_extreme": len(lzma.compress(data, preset=9 | lzma.PRESET_EXTREME)),
    }
    try:
        import brotli
        values["brotli11"] = len(brotli.compress(data, quality=11))
    except Exception:
        pass
    try:
        import zstandard as zstd
        values["zstd19"] = len(
            zstd.ZstdCompressor(level=19, write_checksum=True, write_content_size=True).compress(data)
        )
    except Exception:
        pass
    return values


def run_case(repo: Path, case: dict, history_depth: int, max_file_bytes: int) -> dict:
    model, model_meta = build_repository_model(
        repo, case["base"], history_depth=history_depth, max_file_bytes=max_file_bytes
    )
    target = _blob(repo, case["target"], case["path"])
    target_time = _commit_unix_ns(repo, case["target"])
    target_sha = hashlib.sha256(target).digest()
    if target_sha in model.leakage_guard:
        raise RuntimeError(f"leakage: target already exists in training: {case['name']}")
    if model.max_unix_ns >= target_time:
        raise RuntimeError(f"temporal leakage: training reaches target time: {case['name']}")

    packed = pack_blind_v3(target, case["path"], model, unix_ns=target_time)
    restored = unpack_v3(packed.blob, model)
    if restored != target:
        raise RuntimeError(f"byte equality failed: {case['name']}")
    info = inspect_v3(packed.blob, model)
    baselines = _baselines(target)
    direct_best_name, direct_best_bytes = min(baselines.items(), key=lambda item: (item[1], item[0]))

    return {
        "name": case["name"],
        "base_commit": case["base"],
        "target_commit": case["target"],
        "path": case["path"],
        "target_unix_ns": target_time,
        "target_bytes": len(target),
        "target_git_blob_sha1": _git_blob_sha1(target),
        "target_sha256": target_sha.hex(),
        "target_sha_absent_from_training": True,
        "byte_equal": True,
        "sha256_equal": hashlib.sha256(restored).digest() == target_sha,
        "model": model_meta,
        "qtd3": info,
        "ref_count": packed.ref_count,
        "direct_baselines_bytes": baselines,
        "direct_best_codec": direct_best_name,
        "direct_best_bytes": direct_best_bytes,
        "qtd3_vs_direct_best_reduction_percent":
            100.0 * (1.0 - len(packed.blob) / direct_best_bytes),
        "same_header_direct_best_bytes": direct_best_bytes + info["header_size"],
        "qtd3_vs_same_header_direct_best_reduction_percent":
            100.0 * (1.0 - len(packed.blob) / (direct_best_bytes + info["header_size"])),
        "cold_total_bytes_model_plus_target": model_meta["model_serialized_bytes"] + len(packed.blob),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="QTD3 repository-wide temporal walk-forward benchmark")
    ap.add_argument("repo", type=Path, help="Local git clone to benchmark")
    ap.add_argument("--cases-json", type=Path)
    ap.add_argument("--history-depth", type=int, default=2)
    ap.add_argument("--max-file-bytes", type=int, default=262_144)
    ap.add_argument("-o", "--output", type=Path)
    args = ap.parse_args()

    repo = args.repo.resolve()
    cases = DEFAULT_CASES
    if args.cases_json:
        cases = json.loads(args.cases_json.read_text(encoding="utf-8"))

    rows = [
        run_case(repo, case, args.history_depth, args.max_file_bytes)
        for case in cases
    ]
    total_source = sum(row["target_bytes"] for row in rows)
    total_qtd3 = sum(row["qtd3"]["container_size"] for row in rows)
    total_direct = sum(row["direct_best_bytes"] for row in rows)
    total_covered = sum(row["qtd3"]["covered_bytes"] for row in rows)
    report = {
        "method": "QTD3 repository-wide temporal walk-forward",
        "repo": str(repo),
        "history_depth": args.history_depth,
        "max_file_bytes": args.max_file_bytes,
        "cases": rows,
        "aggregate": {
            "target_count": len(rows),
            "source_bytes": total_source,
            "qtd3_container_bytes": total_qtd3,
            "direct_best_bytes": total_direct,
            "covered_bytes": total_covered,
            "weighted_model_coverage_percent":
                100.0 if total_source == 0 else 100.0 * total_covered / total_source,
            "qtd3_transport_reduction_percent":
                100.0 if total_source == 0 else 100.0 * (1.0-total_qtd3/total_source),
            "qtd3_vs_direct_best_reduction_percent":
                0.0 if total_direct == 0 else 100.0 * (1.0-total_qtd3/total_direct),
        },
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
