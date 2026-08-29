#!/usr/bin/env python3
from __future__ import annotations

import argparse
import bz2
import hashlib
import json
import lzma
import math
from pathlib import Path
import random
import statistics
import time
import zlib

from qr_temporal.container import pack as pack_qtc1, unpack as unpack_qtc1
from qr_temporal.qtc2 import pack_v2, unpack_v2

SEED = 20260730
SIZE = 32768

LEGACY_TOP10 = [
    ("SHTENCO OMNIA TIER1 V2 MAX", 30.335995),
    ("SHTENCO OMNIA TIER1 V2 BALANCED", 27.235040),
    ("SHTENCO GABRIEL-HORN TIER1 MAX", 24.759551),
    ("SHTENCO GABRIEL-HORN TIER1 BALANCED", 24.459013),
    ("SHTENCO GRAAL-IGC TIER1 MAX", 22.633934),
    ("SHTENCO TSC-X TIER1 SPATIAL", 22.114639),
    ("SHTENCO SABF-X ULTIMATE GRAPH-AI", 21.920991),
    ("SHTENCO TSC-X TURBOSPATIAL GRAPH-AI", 21.907299),
    ("SHTENCO HACE-X CASCADE GRAPH-AI", 21.021521),
    ("SHTENCO NEXUS-UMC TIER1", 19.674641),
]


def _repeat(seed: bytes, size: int) -> bytes:
    return (seed * (size // len(seed) + 1))[:size] if seed else bytes(size)


def build_corpus(size: int = SIZE) -> dict[str, bytes]:
    rng = random.Random(SEED)
    code_seed = b'''\nclass GraphAIArchive:\n    def encode_node(self, node, graph):\n        route = node.simhash & 255\n        community = graph.communities[route]\n        parent = community.nearest(node)\n        return parent.xor_patch(node)\n\n    def verify(self, restored, source):\n        return sha256(restored).digest() == sha256(source).digest()\n'''
    source_code = _repeat(code_seed, size)
    records = [json.dumps({
        "timestamp": 1700000000+i, "node": i%97, "route": (i*29)%256,
        "community": (i*7)%31, "event": "graph-edge-verification",
        "status": "PASS" if i%19 else "WARN", "value": round(math.sin(i/17),10),
    }, separators=(",", ":")) for i in range(max(256, size//70))]
    json_logs = _repeat(("\n".join(records)+"\n").encode(), size)
    csv_seed = "time,node,route,price,volume,status\n" + "".join(
        f"{i},{i%43},{(i*17)%256},{100+math.sin(i/23):.8f},{1000+i%211},{'ok' if i%13 else 'warn'}\n"
        for i in range(max(512, size//40)))
    telemetry = _repeat(csv_seed.encode(), size)
    repeated = _repeat(b"SHTENCO-GRAPH-AI-SABF-X-EGD-256-HACE-X\0"*32, size)
    base = bytes((i*13+7)&255 for i in range(1024)); versions=[]
    for version in range(max(32, size//len(base))):
        block=bytearray(base)
        for edit in range(1+version%11):
            block[(version*37+edit*101)%len(block)] ^= (version+edit+1)&255
        versions.append(bytes(block))
    snapshots = _repeat(b"".join(versions), size)
    sparse=bytearray(size)
    for i in range(0,size,89): sparse[i]=rng.randrange(1,256)
    structured=bytearray()
    for i in range(max(512,size//16)):
        structured += i.to_bytes(4,"little")
        structured += ((i*17)%100000).to_bytes(4,"little")
        structured += int(1_000_000+1000*math.sin(i/21)).to_bytes(8,"little",signed=True)
    structured=bytes(structured[:size]).ljust(size,b"\0")
    image=bytearray(); side=max(32,int(math.sqrt(size)))
    for y in range(side+1):
        for x in range(side+1): image.append(((x//8)*11+(y//8)*7+((x+y)//32))&255)
    image_like=_repeat(bytes(image),size)
    words=("abandon ability able about above absent absorb abstract absurd abuse access accident "
           "account accuse achieve acid acoustic acquire across act action actor actress actual adapt ").encode()
    bip39=_repeat(words,size); random_bytes=bytes(rng.randrange(256) for _ in range(size)); fifth=size//5
    mixed=source_code[:fifth]+json_logs[:fifth]+structured[:fifth]+snapshots[:fifth]+random_bytes[:size-4*fifth]
    return {"source_code":source_code,"json_graph_logs":json_logs,"telemetry_csv":telemetry,
            "repeated_text":repeated,"version_snapshots":snapshots,"sparse_weights":bytes(sparse),
            "structured_binary":structured,"image_like":image_like,"bip39_text":bip39,
            "mixed":mixed,"random":random_bytes}


def _gm(values: list[float]) -> float:
    return math.exp(sum(math.log(v) for v in values)/len(values))


def _baseline_sizes(data: bytes) -> dict[str, int]:
    out = {
        "RAW": len(data),
        "zlib-9": len(zlib.compress(data, 9)),
        "bz2-9": len(bz2.compress(data, 9)),
        "lzma-extreme": len(lzma.compress(data, preset=9 | lzma.PRESET_EXTREME)),
    }
    try:
        import brotli
        c = brotli.compress(data, quality=11); assert brotli.decompress(c) == data
        out["brotli-11"] = len(c)
    except Exception:
        pass
    try:
        import zstandard as zstd
        cctx=zstd.ZstdCompressor(level=19); dctx=zstd.ZstdDecompressor()
        c=cctx.compress(data); assert dctx.decompress(c) == data
        out["zstd-19"] = len(c)
    except Exception:
        pass
    return out


def _measure_qtc(data: bytes, repeats: int) -> tuple[dict, dict]:
    q1_enc=[]; q1_dec=[]; q2_enc=[]; q2_dec=[]; q1_sizes=[]; q2_sizes=[]
    digest=hashlib.sha256(data).digest()
    for _ in range(repeats):
        t=time.perf_counter_ns(); p1=pack_qtc1(data); q1_enc.append((time.perf_counter_ns()-t)/1e6)
        t=time.perf_counter_ns(); r1=unpack_qtc1(p1.blob); q1_dec.append((time.perf_counter_ns()-t)/1e6)
        assert r1 == data and hashlib.sha256(r1).digest() == digest
        q1_sizes.append(len(p1.blob))
        t=time.perf_counter_ns(); p2=pack_v2(data, model=None); q2_enc.append((time.perf_counter_ns()-t)/1e6)
        t=time.perf_counter_ns(); r2=unpack_v2(p2.blob, model=None); q2_dec.append((time.perf_counter_ns()-t)/1e6)
        assert r2 == data and hashlib.sha256(r2).digest() == digest
        q2_sizes.append(len(p2.blob))
    def row(sizes, enc, dec):
        size=int(statistics.median(sizes)); e=statistics.median(enc); d=statistics.median(dec); ratio=len(data)/size
        return {"archive_bytes":size,"ratio":ratio,"encode_ms_median":e,"decode_ms_median":d,
                "score_ratio_per_ms":ratio/max(e,.001),"balanced_score":ratio/math.sqrt(max(e,.001)*max(d,.001))}
    return row(q1_sizes,q1_enc,q1_dec), row(q2_sizes,q2_enc,q2_dec)


def main() -> None:
    ap=argparse.ArgumentParser(description="Extend the exact SHTENCO 76-system archive benchmark with QTC1/QTC2")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("-o","--output", type=Path, default=Path("benchmarks/all_archivers_extended_rerun.json"))
    args=ap.parse_args()
    corpus=build_corpus(); rows=[]
    for name,data in corpus.items():
        q1,q2=_measure_qtc(data,args.repeats)
        for engine,row in (("QTC1",q1),("QTC2-standalone",q2)):
            rows.append({"dataset":name,"engine":engine,"original_bytes":len(data),**row,"status":"PASS"})
        for engine,size in _baseline_sizes(data).items():
            rows.append({"dataset":name,"engine":engine,"original_bytes":len(data),"archive_bytes":size,"ratio":len(data)/size,"status":"PASS"})
    summary=[]
    for engine in sorted({r["engine"] for r in rows}):
        items=[r for r in rows if r["engine"]==engine]
        item={"engine":engine,"geomean_ratio":_gm([r["ratio"] for r in items]),"pass":len(items),"total":len(corpus)}
        timed=[r for r in items if "encode_ms_median" in r]
        if timed:
            item.update(geomean_encode_ms=_gm([r["encode_ms_median"] for r in timed]),
                        geomean_decode_ms=_gm([r["decode_ms_median"] for r in timed]),
                        geomean_score=_gm([r["score_ratio_per_ms"] for r in timed]))
        summary.append(item)
    summary.sort(key=lambda x:x["geomean_ratio"], reverse=True)
    new={r["engine"]:r["geomean_ratio"] for r in summary}
    production=LEGACY_TOP10 + [("SHTENCO QTC1 TEMPORAL CONTAINER",new["QTC1"]),
                               ("SHTENCO QTC2 STANDALONE",new["QTC2-standalone"])]
    production=sorted(production,key=lambda x:x[1],reverse=True)[:10]
    report={"schema":"shtenco-all-archivers-extended-rerun","seed":SEED,"dataset_size":SIZE,
            "dataset_count":len(corpus),"repeats":args.repeats,"rows":rows,"summary":summary,
            "legacy_baseline_systems":76,
            "extended_production_top10":[{"rank":i+1,"engine":e,"geomean_ratio":v} for i,(e,v) in enumerate(production)]}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report["extended_production_top10"],ensure_ascii=False,indent=2))

if __name__ == "__main__": main()
