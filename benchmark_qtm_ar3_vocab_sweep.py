#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

from benchmark_qtd3_walkforward import DEFAULT_CASES, _blob, _commit_unix_ns, build_repository_model
from benchmark_qtm_ar2_walkforward import adapt_model
from qr_temporal.qtd41 import pack as pack41
from qr_temporal.qtm_ar2 import pack_unified, unpack_unified
from qr_temporal.qtm_ar3 import pack_temporal, unpack_temporal

PROFILES=(512,4096,8192,16384)


def run_case(repo:Path,case:dict,history_depth:int,max_file_bytes:int):
    model3,meta=build_repository_model(repo,case["base"],history_depth=history_depth,max_file_bytes=max_file_bytes)
    model=adapt_model(model3)
    target=_blob(repo,case["target"],case["path"])
    ts=_commit_unix_ns(repo,case["target"])
    sha=hashlib.sha256(target).digest()
    if sha in model3.leakage_guard:raise RuntimeError("target leakage")
    if model.max_unix_ns>=ts:raise RuntimeError("temporal leakage")

    q41=pack41(target,case["path"],model,ts)
    qau2=pack_unified(target,case["path"],model,ts,q41)
    assert unpack_unified(qau2,model)==target
    profiles={}
    for vocab_size in PROFILES:
        core,timestamps,info=pack_temporal(
            target,case["path"],model,ts,q41_blob=q41,
            vocab_size=vocab_size,min_phrase_len=2,m=1048576,k=1,
        )
        assert unpack_temporal(core,timestamps,model,m=1048576,k=1)==target
        profiles[str(vocab_size)]={
            "core_bytes":len(core),"core_ratio":len(target)/len(core),
            "timestamps":len(timestamps),"materialized_uint64_bytes":8*len(timestamps),
            "materialized_total_bytes":len(core)+8*len(timestamps),**info,
        }
    return {
        "name":case["name"],"path":case["path"],"base_commit":case["base"],"target_commit":case["target"],
        "target_bytes":len(target),"target_sha256":sha.hex(),"qau2_bytes":len(qau2),
        "target_sha_absent_from_training":True,"temporal_cutoff_valid":True,
        "profiles":profiles,"model_bytes":len(model3.to_bytes()),"model_meta":meta,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("repo",type=Path)
    ap.add_argument("--history-depth",type=int,default=2)
    ap.add_argument("--max-file-bytes",type=int,default=262144)
    ap.add_argument("-o","--output",type=Path)
    a=ap.parse_args()
    rows=[run_case(a.repo.resolve(),c,a.history_depth,a.max_file_bytes) for c in DEFAULT_CASES]
    report={"method":"QTM-AR3 variable-vocabulary strict real-Git sweep","profiles":PROFILES,"cases":rows}
    text=json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(text+"\n",encoding="utf-8")
    print(text)


if __name__=="__main__":main()
