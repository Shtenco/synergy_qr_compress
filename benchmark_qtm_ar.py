#!/usr/bin/env python3
"""QTM-AR exact temporal benchmark.

Runs a real README evolution when a local ai_compress git clone is supplied and
also runs two deterministic QTD-style fixtures. Every row is accepted only after
byte equality and SHA-256 equality.
"""
from __future__ import annotations
import argparse, hashlib, json, subprocess
from pathlib import Path
from qr_temporal.qtd41 import Entry, Model, pack as pack_q41, unpack as unpack_q41
from qr_temporal.qtm_ar import pack_ar, unpack_ar, pack_max, unpack_max


def git(repo,*args):return subprocess.check_output(["git","-C",str(repo),*args])
def blob(repo,commit,path):return git(repo,"show",f"{commit}:{path}")
def ctime(repo,commit):return int(git(repo,"show","-s","--format=%ct",commit).strip())*1_000_000_000

def exact_row(name,target,path,model,ts):
    out={"name":name,"source_bytes":len(target),"sha256":hashlib.sha256(target).hexdigest()}
    for label,pack,unpack in (("qtd41",pack_q41,unpack_q41),("qtm_ar",pack_ar,unpack_ar),("qtm_max",pack_max,unpack_max)):
        a=pack(target,path,model,ts);r=unpack(a,model)
        if r!=target or hashlib.sha256(r).digest()!=hashlib.sha256(target).digest():raise RuntimeError(label)
        out[label+"_bytes"]=len(a);out[label+"_ratio"]=len(target)/len(a)
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument("repo",type=Path,nargs="?");ap.add_argument("-o","--output",type=Path);args=ap.parse_args()
    rows=[]
    if args.repo:
        base="9832a2d424b8500bfcc01e088f6119f1419a09bb";target_c="79915e036d80f98be9e72aa6dbd6b37a8d135f45";path="README.md"
        old=blob(args.repo,base,path);target=blob(args.repo,target_c,path)
        m=Model.build([Entry(path,ctime(args.repo,base),old)])
        rows.append(exact_row("real-readme",target,path,m,ctime(args.repo,target_c)))
    m=Model.build([Entry("test_a.py",100,b"import os\n\ndef test_a():\n    source=b'ABC'*100\n    assert source\n"),Entry("test_b.py",110,b"import hashlib\n\ndef test_b():\n    source=b'XYZ'*100\n    assert source\n")])
    rows.append(exact_row("cross-file",b"import os\n\ndef test_c():\n    source=b'ABC'*50\n    assert source\n","test_c.py",m,200))
    old=b"header\nalpha beta gamma\nfooter\n"*20;new=old.replace(b"gamma",b"gamma-v2")+b"new section\n"*10
    m=Model.build([Entry("doc.txt",1000,old)]);rows.append(exact_row("lineage",new,"doc.txt",m,2000))
    report={"method":"QTM-AR strict exact temporal benchmark","rows":rows,"all_exact":True}
    text=json.dumps(report,indent=2,sort_keys=True)
    if args.output:args.output.write_text(text+"\n",encoding="utf-8")
    print(text)

if __name__=="__main__":main()
