#!/usr/bin/env python3
"""Fusion V4.1 compact experiment: COPY-graph deltas + literal context residuals."""
from __future__ import annotations
from dataclasses import dataclass
from difflib import SequenceMatcher
import hashlib, struct, zlib
try: import brotli
except Exception: brotli=None

MAGIC=b"Q41C"; VER=1
RAW,ZLIB,BROTLI=0,1,2
P_RAW,P_LEFT,P_RIGHT,P_BRIDGE,P_LEFTBYTE,P_NGRAM4=range(6)
LINEAGE,EXTERNAL=0,1
H=struct.Struct(">4sBBBBBQ16s32s")

def uv(n):
    o=bytearray()
    while n>=128:o.append((n&127)|128);n>>=7
    o.append(n);return bytes(o)
def rv(b,p=0):
    n=s=0
    while 1:
        q=b[p];p+=1;n|=(q&127)<<s
        if q<128:return n,p
        s+=7
def zz(x):return (x<<1)^(x>>63)
def uz(x):return (x>>1)^-(x&1)

@dataclass(frozen=True)
class Entry:
    path:str; unix_ns:int; data:bytes
    @property
    def digest(self):return hashlib.sha256(self.data).digest()

@dataclass(frozen=True)
class Model:
    entries:tuple[Entry,...]; model_id:bytes
    @classmethod
    def build(cls,rows,model_id=None):
        e=tuple(sorted((Entry(str(x.path),int(x.unix_ns),bytes(x.data)) for x in rows),key=lambda x:(x.unix_ns,x.path,x.digest)))
        raw=b"".join(x.digest+uv(x.unix_ns)+x.path.encode()+b"\0" for x in e)
        return cls(e,model_id or hashlib.sha256(raw).digest())
    @property
    def max_unix_ns(self):return max((x.unix_ns for x in self.entries),default=0)

@dataclass
class Seg:
    op:int; n:int; e:int=-1; off:int=0; pred:int=P_RAW

def lineage(t,path,m):
    c=[(i,e) for i,e in enumerate(m.entries) if e.path==path]
    if not c:return [Seg(0,len(t))]
    ei,b=max(c,key=lambda x:x[1].unix_ns); out=[];p=0
    for z in SequenceMatcher(None,b.data,t,autojunk=False).get_matching_blocks():
        if z.b>p:out.append(Seg(0,z.b-p))
        if z.size:out.append(Seg(1,z.size,ei,z.a))
        p=z.b+z.size
    if p<len(t):out.append(Seg(0,len(t)-p))
    return out

def external(t,path,m,seed=6,mm=12):
    ix={}
    for ei,e in enumerate(m.entries):
        for off in range(max(0,len(e.data)-seed+1)):
            a=ix.setdefault(e.data[off:off+seed],[])
            if len(a)<96:a.append((ei,off))
    same={i for i,e in enumerate(m.entries) if e.path==path}
    out=[];i=ls=0
    def lit(n):
        if n:
            if out and out[-1].op==0:out[-1].n+=n
            else:out.append(Seg(0,n))
    while i<len(t):
        best=(0,-1,0)
        if i+seed<=len(t):
            for ei,off in sorted(ix.get(t[i:i+seed],()),key=lambda x:(0 if x[0] in same else 1,-m.entries[x[0]].unix_ns)):
                s=m.entries[ei].data;n=seed;lim=min(len(t)-i,len(s)-off)
                while n<lim and t[i+n]==s[off+n]:n+=1
                if n>best[0]:best=(n,ei,off)
        if best[0]>=mm:
            lit(i-ls);out.append(Seg(1,best[0],best[1],best[2]));i+=best[0];ls=i
        else:i+=1
    lit(len(t)-ls);return out

def d1(x):
    o=bytearray(len(x));p=0
    for i,a in enumerate(x):o[i]=(a-p)&255;p=a
    return bytes(o)
def ud1(x):
    o=bytearray(len(x));p=0
    for i,a in enumerate(x):p=(p+a)&255;o[i]=p
    return bytes(o)

def ce(x,c):
    if c==RAW:return x
    if c==ZLIB:return zlib.compress(x,9)
    if c==BROTLI and brotli:return brotli.compress(x,quality=11)
    raise ValueError
def cd(x,c):
    if c==RAW:return x
    if c==ZLIB:return zlib.decompress(x)
    if c==BROTLI and brotli:return brotli.decompress(x)
    raise ValueError
def bestc(x):
    a=[]
    for c in (RAW,ZLIB,BROTLI):
        try:
            p=ce(x,c)
            if cd(p,c)==x:a.append((len(p),c,p))
        except:pass
    return min(a)
def bestr(x):
    a=[]
    for tr,y in ((0,x),(1,d1(x)),(2,d1(d1(x)))):
        for c in (RAW,ZLIB,BROTLI):
            try:
                p=ce(y,c);q=cd(p,c)
                if (q if tr==0 else ud1(q) if tr==1 else ud1(ud1(q)))==x:a.append((len(p),tr,c,p))
            except:pass
    return min(a)

_NG={}
def ng4(m):
    k=m.model_id
    if k in _NG:return _NG[k]
    C={}
    for e in m.entries:
        d=e.data
        for i in range(4,len(d)):
            z=C.setdefault(d[i-4:i],{});z[d[i]]=z.get(d[i],0)+1
    T={c:min(v.items(),key=lambda x:(-x[1],x[0]))[0] for c,v in C.items()};_NG[k]=T;return T

def near(segs,i):
    for j in range(i-1,-1,-1):
        if segs[j].op:return segs[j]
    return None
def nextc(segs,i):
    for j in range(i+1,len(segs)):
        if segs[j].op:return segs[j]
    return None

def res(mode,lit,segs,i,m,prefix,decode=False):
    if mode==P_NGRAM4:
        T=ng4(m);h=bytearray(prefix);o=bytearray()
        for a in lit:
            q=T.get(bytes(h[-4:]),0) if len(h)>=4 else 0
            x=a^q;o.append(x);h.append(x if decode else a)
        return bytes(o)
    n=len(lit);a=near(segs,i);b=nextc(segs,i);L=R=bytes(n)
    if a:
        s=m.entries[a.e].data[a.off+a.n:a.off+a.n+n];L=s+bytes(n-len(s))
    if b:
        s=m.entries[b.e].data[max(0,b.off-n):b.off];R=bytes(n-len(s))+s
    if mode==P_RAW:P=bytes(n)
    elif mode==P_LEFT:P=L
    elif mode==P_RIGHT:P=R
    elif mode==P_BRIDGE:P=L[:n//2]+R[n//2:]
    else:P=bytes([prefix[-1] if prefix else 0])*n
    return bytes(x^y for x,y in zip(lit,P))

def choose(t,segs,m):
    pos=0;out=bytearray();rr=bytearray()
    for i,s in enumerate(segs):
        if s.op:
            x=m.entries[s.e].data[s.off:s.off+s.n];out+=x;pos+=s.n;continue
        lit=t[pos:pos+s.n];best=None
        for pm in range(6):
            r=res(pm,lit,segs,i,m,bytes(out))
            cost=min(len(r),len(zlib.compress(r,6)),len(brotli.compress(r,quality=5)) if brotli else 10**9)
            z=(cost,pm,r)
            if best is None or z[:2]<best[:2]:best=z
        s.pred=best[1];rr+=best[2];out+=lit;pos+=s.n
    return bytes(rr)

def skenc(segs):
    o=bytearray();pe=po=pl=0
    for s in segs:
        if not s.op:o+=b"\0"+uv(s.n)+bytes([s.pred])
        else:
            o.append(1);o+=uv(zz(s.e-pe));pred=po+pl if s.e==pe else 0
            o+=uv(zz(s.off-pred))+uv(zz(s.n-pl));pe,po,pl=s.e,s.off,s.n
    return bytes(o)
def skdec(b):
    o=[];p=0;pe=po=pl=0
    while p<len(b):
        op=b[p];p+=1
        if not op:
            n,p=rv(b,p);pm=b[p];p+=1;o.append(Seg(0,n,pred=pm))
        else:
            a,p=rv(b,p);c,p=rv(b,p);d,p=rv(b,p);e=pe+uz(a);pred=po+pl if e==pe else 0
            off=pred+uz(c);n=pl+uz(d);o.append(Seg(1,n,e,off));pe,po,pl=e,off,n
    return o

def rebuild(segs,rr,m):
    o=bytearray();p=0
    for i,s in enumerate(segs):
        if s.op:o+=m.entries[s.e].data[s.off:s.off+s.n]
        else:
            r=rr[p:p+s.n];x=res(s.pred,r,segs,i,m,bytes(o),True);o+=x;p+=s.n
    if p!=len(rr):raise ValueError
    return bytes(o)

def one(t,segs,m,ts,strategy):
    segs=[Seg(x.op,x.n,x.e,x.off,x.pred) for x in segs];rr=choose(t,segs,m);sk=skenc(segs)
    _,sc,sp=bestc(sk);_,tr,rc,rp=bestr(rr)
    h=H.pack(MAGIC,VER,strategy,sc,tr,rc,ts,m.model_id[:16],hashlib.sha256(t).digest())
    return h+uv(len(t))+uv(len(sp))+sp+rp

def pack(t,path,m,ts):
    t=bytes(t)
    if m.max_unix_ns>=ts or any(e.digest==hashlib.sha256(t).digest() for e in m.entries):raise ValueError("leakage")
    R=[(LINEAGE,lineage(t,path,m))]
    for seed in (4,5,6,8,10):
        for mm in (8,10,12,16,24,32):
            if mm>=seed:R.append((EXTERNAL,external(t,path,m,seed,mm)))
    a=[];seen=set()
    for st,segs in R:
        sig=tuple((x.op,x.n,x.e,x.off) for x in segs)
        if sig in seen or sum(x.n for x in segs)!=len(t):continue
        seen.add(sig)
        try:
            b=one(t,segs,m,ts,st)
            if unpack(b,m)==t:a.append((len(b),b))
        except:pass
    return min(a)[1]

def unpack(b,m):
    magic,v,st,sc,tr,rc,ts,mid,dg=H.unpack_from(b)
    if magic!=MAGIC or v!=VER or mid!=m.model_id[:16] or m.max_unix_ns>=ts:raise ValueError
    p=H.size;n,p=rv(b,p);sn,p=rv(b,p);sk=skdec(cd(b[p:p+sn],sc));q=cd(b[p+sn:],rc)
    rr=q if tr==0 else ud1(q) if tr==1 else ud1(ud1(q))
    if len(rr)!=sum(x.n for x in sk if not x.op) or sum(x.n for x in sk)!=n:raise ValueError
    t=rebuild(sk,rr,m)
    if hashlib.sha256(t).digest()!=dg:raise ValueError
    return t

def inspect(b,m=None):
    magic,v,st,sc,tr,rc,ts,mid,dg=H.unpack_from(b);p=H.size;n,p=rv(b,p);sn,p=rv(b,p)
    sk=skdec(cd(b[p:p+sn],sc));lit=sum(x.n for x in sk if not x.op)
    return {"container_size":len(b),"original_size":n,"ratio":n/len(b),"strategy":st,
            "covered_bytes":n-lit,"coverage_percent":100*(n-lit)/n if n else 100,
            "literal_bytes":lit,"header_varint_bytes":p,"skeleton_bytes":sn,
            "model_match":None if m is None else mid==m.model_id[:16]}
