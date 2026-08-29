#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

from benchmark_qtd3_walkforward import (
    DEFAULT_CASES, _baselines, _blob, _commit_unix_ns, build_repository_model
)
from qr_temporal.qtd3 import pack_blind_v3, unpack_v3
from qr_temporal.qtd41 import Entry, Model, pack as pack41, unpack as unpack41
from qr_temporal.qtm_ar import pack_ar, unpack_ar
from qr_temporal.qtm_ar2 import pack_ar2, unpack_ar2, pack_unified, unpack_unified, temporal_stats


def adapt_model(model3):
    return Model(tuple(Entry(e.path,e.unix_ns,e.data) for e in model3.entries), model3.model_id)


def run_case(repo:Path,case:dict,history_depth:int,max_file_bytes:int):
    model3,meta=build_repository_model(repo,case["base"],history_depth=history_depth,max_file_bytes=max_file_bytes)
    model=adapt_model(model3)
    target=_blob(repo,case["target"],case["path"])
    ts=_commit_unix_ns(repo,case["target"])
    sha=hashlib.sha256(target).digest()
    if sha in model3.leakage_guard:raise RuntimeError("target leakage")
    if model.max_unix_ns>=ts:raise RuntimeError("temporal leakage")

    q3=pack_blind_v3(target,case["path"],model3,unix_ns=ts).blob
    q41=pack41(target,case["path"],model,ts)
    q1=pack_ar(target,case["path"],model,ts,q41)
    q2=pack_ar2(target,case["path"],model,ts,q41)
    qu=pack_unified(target,case["path"],model,ts,q41)
    best=min((q41,q1,q2,qu),key=lambda b:(len(b),b[:4]))

    assert unpack_v3(q3,model3)==target
    assert unpack41(q41,model)==target
    assert unpack_ar(q1,model)==target
    assert unpack_ar2(q2,model)==target
    assert unpack_unified(qu,model)==target
    if best[:4]==b"QAU2":assert unpack_unified(best,model)==target
    elif best[:4]==b"QA22":assert unpack_ar2(best,model)==target
    elif best[:4]==b"QAR1":assert unpack_ar(best,model)==target
    else:assert unpack41(best,model)==target

    bases=_baselines(target)
    return {
        "name":case["name"],"base_commit":case["base"],"target_commit":case["target"],"path":case["path"],
        "target_bytes":len(target),"target_sha256":sha.hex(),
        "target_sha_absent_from_training":True,"temporal_cutoff_valid":True,
        "qtd3_bytes":len(q3),"qtd41_bytes":len(q41),"qtm_ar1_bytes":len(q1),
        "qtm_ar2_bytes":len(q2),"qtm_ar2_unified_bytes":len(qu),"qtm_ar2_max_bytes":len(best),
        "qtm_ar2_max_magic":best[:4].decode("latin1"),
        "direct_baselines":bases,
        "temporal_carrier_256x32":temporal_stats(len(best),256,32),
        "temporal_carrier_16384x12":temporal_stats(len(best),16384,12),
        "temporal_carrier_65536x8":temporal_stats(len(best),65536,8),
        "model_bytes":len(model3.to_bytes()),"model_meta":meta,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("repo",type=Path)
    ap.add_argument("--history-depth",type=int,default=2)
    ap.add_argument("--max-file-bytes",type=int,default=262144)
    ap.add_argument("-o","--output",type=Path)
    a=ap.parse_args()
    rows=[run_case(a.repo.resolve(),c,a.history_depth,a.max_file_bytes) for c in DEFAULT_CASES]
    source=sum(x["target_bytes"] for x in rows)
    report={
        "method":"QTM-AR2 strict real-Git temporal walk-forward",
        "cases":rows,
        "aggregate":{
            "source_bytes":source,
            "qtd3_bytes":sum(x["qtd3_bytes"] for x in rows),
            "qtd41_bytes":sum(x["qtd41_bytes"] for x in rows),
            "qtm_ar1_bytes":sum(x["qtm_ar1_bytes"] for x in rows),
            "qtm_ar2_bytes":sum(x["qtm_ar2_bytes"] for x in rows),
            "qtm_ar2_unified_bytes":sum(x["qtm_ar2_unified_bytes"] for x in rows),
            "qtm_ar2_max_bytes":sum(x["qtm_ar2_max_bytes"] for x in rows),
            "all_target_sha_absent_from_training":all(x["target_sha_absent_from_training"] for x in rows),
            "all_temporal_cutoff_valid":all(x["temporal_cutoff_valid"] for x in rows),
        }
    }
    text=json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(text+"\n",encoding="utf-8")
    print(text)


if __name__=="__main__":main()
