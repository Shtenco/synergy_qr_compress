#!/usr/bin/env python3
"""QTM-AR: timestamp-weighted temporal probabilistic ML + arithmetic coding."""
from __future__ import annotations
import hashlib, struct
from . import qtd41 as q41

MAGIC=b"QAR1";VER=1
H=struct.Struct(">4sBBBQ16s32s")
TOP=1<<32; HALF=1<<31; Q1=1<<30; Q3=3<<30


def _time_weight(entry_ts,target_ts):
    age=max(0,target_ts-entry_ts);hours=age//3_600_000_000_000
    return max(1,256>>min(8,(hours+1).bit_length()-1))


class ProbModel:
    def __init__(self,model,path_index,target_ts):
        self.global_counts={};self.hist={k:{} for k in range(1,7)};self.adapt={k:{} for k in range(1,7)};self.same=None
        wanted=model.entries[path_index].path if 0<=path_index<len(model.entries) else None
        same=[e for e in model.entries if wanted is not None and e.path==wanted and e.unix_ns<target_ts]
        if same:self.same=max(same,key=lambda e:e.unix_ns)
        for e in model.entries:
            if e.unix_ns>=target_ts:continue
            tw=_time_weight(e.unix_ns,target_ts)*(2 if wanted is not None and e.path==wanted else 1);d=e.data
            for x in d:self.global_counts[x]=self.global_counts.get(x,0)+tw
            for k in range(1,7):
                tab=self.hist[k]
                for i in range(k,len(d)):
                    b=tab.setdefault(d[i-k:i],{});b[d[i]]=b.get(d[i],0)+tw

    def frequencies(self,history,pos):
        f=[1]*256
        for b,c in self.global_counts.items():f[b]+=max(1,c//64)
        for k in range(1,7):
            if len(history)<k:continue
            ctx=history[-k:];bucket=self.hist[k].get(ctx)
            if bucket:
                mult=1<<(k-1)
                for b,c in bucket.items():f[b]+=c*mult
            ab=self.adapt[k].get(ctx)
            if ab:
                mult=16*(1<<(k-1))
                for b,c in ab.items():f[b]+=c*mult
        if self.same is not None and pos<len(self.same.data):f[self.same.data[pos]]+=256
        if history:
            f[history[-1]]+=16
            if len(history)>=2:f[(2*history[-1]-history[-2])&255]+=8
        total=sum(f)
        if total>32768:
            scale=(total+32767)//32768;f=[max(1,x//scale) for x in f]
        return f

    def update(self,history,actual):
        for k in range(1,7):
            if len(history)<k:continue
            b=self.adapt[k].setdefault(history[-k:],{});b[actual]=min(255,b.get(actual,0)+1)


class BW:
    def __init__(self):self.o=bytearray();self.c=0;self.n=0
    def bit(self,b):
        self.c=(self.c<<1)|(b&1);self.n+=1
        if self.n==8:self.o.append(self.c);self.c=self.n=0
    def finish(self):
        if self.n:self.o.append(self.c<<(8-self.n))
        return bytes(self.o)

class BR:
    def __init__(self,b):self.b=b;self.p=0
    def bit(self):
        if self.p>=len(self.b)*8:self.p+=1;return 0
        v=(self.b[self.p>>3]>>(7-(self.p&7)))&1;self.p+=1;return v


def _cum(f):
    c=[0];s=0
    for x in f:s+=x;c.append(s)
    return c


class ArithmeticEncoder:
    def __init__(self):self.low=0;self.high=TOP-1;self.pending=0;self.bw=BW()
    def _emit(self,b):
        self.bw.bit(b);inv=1-b
        for _ in range(self.pending):self.bw.bit(inv)
        self.pending=0
    def symbol(self,sym,freq):
        c=_cum(freq);total=c[-1];rng=self.high-self.low+1
        self.high=self.low+(rng*c[sym+1]//total)-1;self.low=self.low+(rng*c[sym]//total)
        while True:
            if self.high<HALF:self._emit(0)
            elif self.low>=HALF:self._emit(1);self.low-=HALF;self.high-=HALF
            elif self.low>=Q1 and self.high<Q3:self.pending+=1;self.low-=Q1;self.high-=Q1
            else:break
            self.low=(self.low<<1)&(TOP-1);self.high=((self.high<<1)&(TOP-1))|1
    def finish(self):self.pending+=1;self._emit(0 if self.low<Q1 else 1);return self.bw.finish()


class ArithmeticDecoder:
    def __init__(self,b):
        self.br=BR(b);self.low=0;self.high=TOP-1;self.code=0
        for _ in range(32):self.code=((self.code<<1)|self.br.bit())&(TOP-1)
    def symbol(self,freq):
        c=_cum(freq);total=c[-1];rng=self.high-self.low+1;value=((self.code-self.low+1)*total-1)//rng
        lo=0;hi=256
        while lo+1<hi:
            m=(lo+hi)//2
            if c[m]<=value:lo=m
            else:hi=m
        sym=lo;self.high=self.low+(rng*c[sym+1]//total)-1;self.low=self.low+(rng*c[sym]//total)
        while True:
            if self.high<HALF:pass
            elif self.low>=HALF:self.low-=HALF;self.high-=HALF;self.code-=HALF
            elif self.low>=Q1 and self.high<Q3:self.low-=Q1;self.high-=Q1;self.code-=Q1
            else:break
            self.low=(self.low<<1)&(TOP-1);self.high=((self.high<<1)&(TOP-1))|1;self.code=((self.code<<1)&(TOP-1))|self.br.bit()
        return sym


def path_index(path,model):
    a=[(i,e) for i,e in enumerate(model.entries) if e.path==path]
    return max(a,key=lambda x:x[1].unix_ns)[0] if a else len(model.entries)


def q41_segments(blob):
    magic,v,st,sc,tr,rc,ts,mid,dg=q41.H.unpack_from(blob);p=q41.H.size;n,p=q41.rv(blob,p);sn,p=q41.rv(blob,p)
    return st,[q41.Seg(x.op,x.n,x.e,x.off,0) for x in q41.skdec(q41.cd(blob[p:p+sn],sc))]


def encode_literals(target,segs,model,pi,ts):
    pm=ProbModel(model,pi,ts);ae=ArithmeticEncoder();out=bytearray();pos=0
    for s in segs:
        if s.op:
            chunk=model.entries[s.e].data[s.off:s.off+s.n]
            for x in chunk:hist=bytes(out);pm.update(hist,x);out.append(x)
            pos+=s.n
        else:
            for x in target[pos:pos+s.n]:
                hist=bytes(out);ae.symbol(x,pm.frequencies(hist,len(out)));pm.update(hist,x);out.append(x)
            pos+=s.n
    if bytes(out)!=target:raise ValueError("ML traversal mismatch")
    return ae.finish()


def decode_literals(bits,segs,model,pi,ts):
    pm=ProbModel(model,pi,ts);ad=ArithmeticDecoder(bits);out=bytearray()
    for s in segs:
        if s.op:
            chunk=model.entries[s.e].data[s.off:s.off+s.n]
            for x in chunk:hist=bytes(out);pm.update(hist,x);out.append(x)
        else:
            for _ in range(s.n):
                hist=bytes(out);x=ad.symbol(pm.frequencies(hist,len(out)));pm.update(hist,x);out.append(x)
    return bytes(out)


def pack_ar(target,path,model,ts,q41_blob=None):
    target=bytes(target)
    if model.max_unix_ns>=ts or any(e.digest==hashlib.sha256(target).digest() for e in model.entries):raise ValueError("leakage")
    if q41_blob is None:q41_blob=q41.pack(target,path,model,ts)
    st,segs=q41_segments(q41_blob);pi=path_index(path,model);bits=encode_literals(target,segs,model,pi,ts)
    for s in segs:
        if not s.op:s.pred=0
    sk=q41.skenc(segs);_,sc,sp=q41.bestc(sk);h=H.pack(MAGIC,VER,st,sc,ts,model.model_id[:16],hashlib.sha256(target).digest())
    return h+q41.uv(len(target))+q41.uv(pi)+q41.uv(len(sp))+sp+bits


def unpack_ar(blob,model):
    magic,v,st,sc,ts,mid,dg=H.unpack_from(blob)
    if magic!=MAGIC or v!=VER or mid!=model.model_id[:16] or model.max_unix_ns>=ts:raise ValueError("bad model")
    p=H.size;n,p=q41.rv(blob,p);pi,p=q41.rv(blob,p);sn,p=q41.rv(blob,p);segs=q41.skdec(q41.cd(blob[p:p+sn],sc))
    if sum(x.n for x in segs)!=n:raise ValueError("size mismatch")
    target=decode_literals(blob[p+sn:],segs,model,pi,ts)
    if len(target)!=n or hashlib.sha256(target).digest()!=dg:raise ValueError("exactness")
    return target


def pack_max(target,path,model,ts):
    a=q41.pack(target,path,model,ts);b=pack_ar(target,path,model,ts,a);return min((a,b),key=lambda x:(len(x),x[:4]))

def unpack_max(blob,model):return unpack_ar(blob,model) if blob[:4]==MAGIC else q41.unpack(blob,model)
