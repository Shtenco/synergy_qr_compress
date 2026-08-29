#!/usr/bin/env python3
"""
QTM-AR2: temporal ML for BOTH QTD COPY-graph and literal bytes.

Warm/shared model:
- target is strictly newer than all model entries;
- target SHA-256 must be absent from training;
- COPY/LITERAL skeleton is learned from older revisions and arithmetic-coded;
- literal bytes use QTM-AR timestamp-weighted order-1..6 probability model;
- exact SHA-256 guarded round-trip.

Temporal Combination Carrier:
- combines centered 20-bit nanosecond jitter states with combinadic selection
  of K timestamp slots among M candidates;
- exactly reversible;
- carrier event count/span are separate from ordinary byte compression.
"""
from __future__ import annotations
import hashlib, math, struct

from . import qtd41 as q41
from . import qtm_ar as ar1

MAGIC=b"QA22"; VER=1
H=struct.Struct(">4sBBQ16s32s")

F_LIT_LEN=0; F_ENTRY=1; F_OFFSET=2; F_COPY_LEN=3
FIELD_COUNT=4

W_NS=1<<20
CENTER=1<<19


def zz(x:int)->int:return (x<<1)^(x>>63)
def unzz(x:int)->int:return (x>>1)^-(x&1)


class GenericArithmeticDecoder:
    """QTM-AR decoder generalized from 256 symbols to arbitrary alphabet size."""
    def __init__(self,b):
        self.br=ar1.BR(b);self.low=0;self.high=ar1.TOP-1;self.code=0
        for _ in range(32):
            self.code=((self.code<<1)|self.br.bit())&(ar1.TOP-1)

    def symbol(self,freq):
        c=[0];total0=0
        for x in freq:total0+=x;c.append(total0)
        total=c[-1];rng=self.high-self.low+1
        value=((self.code-self.low+1)*total-1)//rng
        lo=0;hi=len(freq)
        while lo+1<hi:
            mid=(lo+hi)//2
            if c[mid]<=value:lo=mid
            else:hi=mid
        sym=lo
        self.high=self.low+(rng*c[sym+1]//total)-1
        self.low=self.low+(rng*c[sym]//total)
        while True:
            if self.high<ar1.HALF:
                pass
            elif self.low>=ar1.HALF:
                self.low-=ar1.HALF;self.high-=ar1.HALF;self.code-=ar1.HALF
            elif self.low>=ar1.Q1 and self.high<ar1.Q3:
                self.low-=ar1.Q1;self.high-=ar1.Q1;self.code-=ar1.Q1
            else:
                break
            self.low=(self.low<<1)&(ar1.TOP-1)
            self.high=((self.high<<1)&(ar1.TOP-1))|1
            self.code=((self.code<<1)&(ar1.TOP-1))|self.br.bit()
        return sym


def _time_weight(entry_ts:int,target_ts:int)->int:
    age=max(0,target_ts-entry_ts)
    hours=age//3_600_000_000_000
    return max(1,256>>min(8,(hours+1).bit_length()-1))


def _historical_linear_segments(prev:bytes,cur:bytes,min_copy:int=8):
    """O(n) same-position historical COPY prior; never used to encode target."""
    n=len(cur);m=min(len(prev),n);out=[];i=0;lit=0
    def flush():
        nonlocal lit
        if lit:
            if out and not out[-1].op:out[-1].n+=lit
            else:out.append(q41.Seg(0,lit))
            lit=0
    while i<m:
        if prev[i]==cur[i]:
            j=i+1
            while j<m and prev[j]==cur[j]:j+=1
            run=j-i
            if run>=min_copy:
                flush();out.append(q41.Seg(1,run,0,i))
            else:lit+=run
            i=j
        else:
            lit+=1;i+=1
    if i<n:lit+=n-i
    flush()
    return out


def _events(segs):
    pe=po=pl=0;prev_lit=0
    for s in segs:
        if not s.op:
            yield ("op",0)
            yield ("int",F_LIT_LEN,zz(s.n-prev_lit))
            prev_lit=s.n
        else:
            yield ("op",1)
            yield ("int",F_ENTRY,zz(s.e-pe))
            pred=po+pl if s.e==pe else 0
            yield ("int",F_OFFSET,zz(s.off-pred))
            yield ("int",F_COPY_LEN,zz(s.n-pl))
            pe,po,pl=s.e,s.off,s.n


class SkeletonProbModel:
    def __init__(self,model,path,target_ts):
        self.op=[1,1];self.ad_op=[0,0]
        self.fields=[[[1]*256 for _ in range(6)] for __ in range(FIELD_COUNT)]
        self.ad_fields=[[[0]*256 for _ in range(6)] for __ in range(FIELD_COUNT)]
        hist=sorted([e for e in model.entries if e.path==path and e.unix_ns<target_ts],key=lambda e:e.unix_ns)
        for j in range(1,len(hist)):
            prev,cur=hist[j-1],hist[j]
            tw=_time_weight(cur.unix_ns,target_ts)
            for ev in _events(_historical_linear_segments(prev.data,cur.data)):
                if ev[0]=="op":self.op[ev[1]]+=tw
                else:
                    _,field,n=ev
                    for pos,b in enumerate(q41.uv(n)):
                        if pos>=6:break
                        self.fields[field][pos][b]+=tw

    def op_freq(self):return [self.op[i]+8*self.ad_op[i] for i in range(2)]
    def update_op(self,x):self.ad_op[x]=min(255,self.ad_op[x]+1)
    def field_freq(self,field,pos):
        p=min(pos,5)
        return [self.fields[field][p][b]+16*self.ad_fields[field][p][b] for b in range(256)]
    def update_field(self,field,pos,b):
        p=min(pos,5);self.ad_fields[field][p][b]=min(255,self.ad_fields[field][p][b]+1)


def _enc_int(ae,pm,field,n):
    for pos,b in enumerate(q41.uv(n)):
        ae.symbol(b,pm.field_freq(field,pos));pm.update_field(field,pos,b)


def _dec_int(ad,pm,field):
    raw=bytearray();pos=0
    while True:
        b=ad.symbol(pm.field_freq(field,pos));pm.update_field(field,pos,b)
        raw.append(b);pos+=1
        if b<128:break
        if pos>10:raise ValueError("varint too long")
    n,p=q41.rv(bytes(raw),0)
    if p!=len(raw):raise ValueError("varint parse")
    return n


def encode_skeleton(segs,model,path,ts):
    pm=SkeletonProbModel(model,path,ts);ae=ar1.ArithmeticEncoder()
    pe=po=pl=0;prev_lit=0
    for s in segs:
        op=1 if s.op else 0
        ae.symbol(op,pm.op_freq());pm.update_op(op)
        if not op:
            _enc_int(ae,pm,F_LIT_LEN,zz(s.n-prev_lit));prev_lit=s.n
        else:
            _enc_int(ae,pm,F_ENTRY,zz(s.e-pe))
            pred=po+pl if s.e==pe else 0
            _enc_int(ae,pm,F_OFFSET,zz(s.off-pred))
            _enc_int(ae,pm,F_COPY_LEN,zz(s.n-pl))
            pe,po,pl=s.e,s.off,s.n
    return ae.finish(),len(segs)


def decode_skeleton(bits,count,model,path,ts):
    pm=SkeletonProbModel(model,path,ts);ad=GenericArithmeticDecoder(bits)
    out=[];pe=po=pl=0;prev_lit=0
    for _ in range(count):
        op=ad.symbol(pm.op_freq());pm.update_op(op)
        if not op:
            n=prev_lit+unzz(_dec_int(ad,pm,F_LIT_LEN))
            if n<=0:raise ValueError("literal length")
            out.append(q41.Seg(0,n));prev_lit=n
        else:
            e=pe+unzz(_dec_int(ad,pm,F_ENTRY))
            pred=po+pl if e==pe else 0
            off=pred+unzz(_dec_int(ad,pm,F_OFFSET))
            n=pl+unzz(_dec_int(ad,pm,F_COPY_LEN))
            if e<0 or off<0 or n<=0:raise ValueError("copy field")
            out.append(q41.Seg(1,n,e,off));pe,po,pl=e,off,n
    return out


def pack_ar2(target,path,model,ts,q41_blob=None):
    target=bytes(target);digest=hashlib.sha256(target).digest()
    if model.max_unix_ns>=ts or any(e.digest==digest for e in model.entries):raise ValueError("leakage")
    if q41_blob is None:q41_blob=q41.pack(target,path,model,ts)
    st,segs=ar1.q41_segments(q41_blob);pi=ar1.path_index(path,model)
    sk,count=encode_skeleton(segs,model,path,ts)
    lit=ar1.encode_literals(target,segs,model,pi,ts)
    if isinstance(lit,tuple):lit=lit[0]
    out=bytearray(H.pack(MAGIC,VER,st,ts,model.model_id[:16],digest)+q41.uv(len(target))+q41.uv(pi))
    if pi>=len(model.entries):
        pb=path.encode("utf-8");out+=q41.uv(len(pb))+pb
    out+=q41.uv(count)+q41.uv(len(sk))+sk+lit
    return bytes(out)


def unpack_ar2(blob,model):
    magic,v,st,ts,mid,digest=H.unpack_from(blob)
    if magic!=MAGIC or v!=VER or mid!=model.model_id[:16] or model.max_unix_ns>=ts:raise ValueError("model/header")
    p=H.size;n,p=q41.rv(blob,p);pi,p=q41.rv(blob,p)
    if pi<len(model.entries):path=model.entries[pi].path
    else:
        plen,p=q41.rv(blob,p);path=blob[p:p+plen].decode("utf-8");p+=plen
    count,p=q41.rv(blob,p);sn,p=q41.rv(blob,p)
    segs=decode_skeleton(blob[p:p+sn],count,model,path,ts)
    if sum(s.n for s in segs)!=n:raise ValueError("segment total")
    target=ar1.decode_literals(blob[p+sn:],segs,model,pi,ts)
    if len(target)!=n or hashlib.sha256(target).digest()!=digest:raise ValueError("exactness")
    return target


# ---------- timestamp combination layer ----------

def comb_rank(combo):return sum(math.comb(c,i+1) for i,c in enumerate(combo))


def comb_unrank(rank,k,m):
    if rank<0 or rank>=math.comb(m,k):raise ValueError("rank")
    c=[0]*k;r=rank;upper=m-1
    for i in range(k,0,-1):
        lo=i-1;hi=upper
        while lo<hi:
            mid=(lo+hi+1)//2
            if math.comb(mid,i)<=r:lo=mid
            else:hi=mid-1
        c[i-1]=lo;r-=math.comb(lo,i);upper=lo-1
    return c


def temporal_capacity(m=65536,k=8):
    cbits=math.comb(m,k).bit_length()-1
    return {"m":m,"k":k,"comb_bits":cbits,"jitter_bits":20*k,
            "bits_per_block":cbits+20*k,"bits_per_timestamp":(cbits+20*k)/k,
            "block_span_seconds":(m+1)*W_NS/1e9}


def _bits(data):
    return [(x>>i)&1 for x in data for i in range(7,-1,-1)]


def _take(bits,p,n):
    v=0
    for i in range(n):v=(v<<1)|(bits[p+i] if p+i<len(bits) else 0)
    return v,p+n


def _put(out,v,n):
    for i in range(n-1,-1,-1):out.append((v>>i)&1)


def temporal_encode(blob,anchor_ns=1_800_000_000_000_000_000,m=65536,k=8):
    anchor=(anchor_ns//W_NS)*W_NS
    bits=_bits(struct.pack(">Q",len(blob))+blob)
    cbits=math.comb(m,k).bit_length()-1;per=cbits+20*k
    blocks=(len(bits)+per-1)//per;ts=[anchor];p=0
    for b in range(blocks):
        rank,p=_take(bits,p,cbits);combo=comb_unrank(rank,k,m)
        residual=[]
        for _ in range(k):
            x,p=_take(bits,p,20);residual.append(x-CENTER)
        base=anchor+(1+b*(m+1))*W_NS
        ts.extend(base+slot*W_NS+j for slot,j in zip(combo,residual))
    if any(b<=a for a,b in zip(ts,ts[1:])):raise ValueError("order")
    return ts


def temporal_decode(ts,m=65536,k=8):
    if not ts or (len(ts)-1)%k:raise ValueError("stream")
    anchor=ts[0];cbits=math.comb(m,k).bit_length()-1;out=[]
    for b in range((len(ts)-1)//k):
        group=ts[1+b*k:1+(b+1)*k];base=anchor+(1+b*(m+1))*W_NS
        combo=[];res=[]
        for t in group:
            slot=(t-base+CENTER)//W_NS;grid=base+slot*W_NS;j=t-grid
            if slot<0 or slot>=m or j<-CENTER or j>=CENTER:raise ValueError("point")
            combo.append(int(slot));res.append(int(j+CENTER))
        rank=comb_rank(combo)
        if rank>=(1<<cbits):raise ValueError("subset")
        _put(out,rank,cbits)
        for x in res:_put(out,x,20)
    raw=bytearray()
    for p in range(0,len(out)//8*8,8):
        v=0
        for b in out[p:p+8]:v=(v<<1)|b
        raw.append(v)
    if len(raw)<8:raise ValueError("short")
    n=struct.unpack(">Q",raw[:8])[0]
    if 8+n>len(raw):raise ValueError("payload")
    return bytes(raw[8:8+n])


def temporal_stats(blob_len,m=65536,k=8):
    c=temporal_capacity(m,k);bits=(8+blob_len)*8
    blocks=math.ceil(bits/c["bits_per_block"]);events=1+blocks*k
    span=(1+(blocks-1)*(m+1)+(m-1))*W_NS/1e9 if blocks else 0
    return {**c,"blob_bytes":blob_len,"framed_bits":bits,"blocks":blocks,
            "timestamps":events,"materialized_uint64_bytes":events*8,
            "timeline_span_seconds":span}


# ---------- unified arithmetic state: skeleton + literals ----------

MAGIC_U=b"QAU2"
PATH_ID_FLAG=0x40
PATH_EXPLICIT_FLAG=0x80


def _path_meta_encode(path,model,strategy):
    paths=sorted(set(e.path for e in model.entries))
    if path in paths:
        if len(paths)==1:return strategy,b""
        return strategy|PATH_ID_FLAG,q41.uv(paths.index(path))
    pb=path.encode("utf-8")
    return strategy|PATH_EXPLICIT_FLAG,q41.uv(len(pb))+pb


def _path_meta_decode(blob,p,model,flags):
    paths=sorted(set(e.path for e in model.entries))
    if flags&PATH_EXPLICIT_FLAG:
        n,p=q41.rv(blob,p);path=blob[p:p+n].decode("utf-8");p+=n
    elif flags&PATH_ID_FLAG:
        idx,p=q41.rv(blob,p)
        if idx>=len(paths):raise ValueError("path id")
        path=paths[idx]
    else:
        if len(paths)!=1:raise ValueError("ambiguous shared path")
        path=paths[0]
    return path,p


def _encode_skeleton_into(ae,segs,model,path,ts):
    pm=SkeletonProbModel(model,path,ts);pe=po=pl=0;prev_lit=0
    for s in segs:
        op=1 if s.op else 0
        ae.symbol(op,pm.op_freq());pm.update_op(op)
        if not op:
            _enc_int(ae,pm,F_LIT_LEN,zz(s.n-prev_lit));prev_lit=s.n
        else:
            _enc_int(ae,pm,F_ENTRY,zz(s.e-pe))
            pred=po+pl if s.e==pe else 0
            _enc_int(ae,pm,F_OFFSET,zz(s.off-pred))
            _enc_int(ae,pm,F_COPY_LEN,zz(s.n-pl))
            pe,po,pl=s.e,s.off,s.n


def _decode_skeleton_from(ad,count,model,path,ts):
    pm=SkeletonProbModel(model,path,ts);out=[];pe=po=pl=0;prev_lit=0
    for _ in range(count):
        op=ad.symbol(pm.op_freq());pm.update_op(op)
        if not op:
            n=prev_lit+unzz(_dec_int(ad,pm,F_LIT_LEN))
            if n<=0:raise ValueError("literal length")
            out.append(q41.Seg(0,n));prev_lit=n
        else:
            e=pe+unzz(_dec_int(ad,pm,F_ENTRY))
            pred=po+pl if e==pe else 0
            off=pred+unzz(_dec_int(ad,pm,F_OFFSET))
            n=pl+unzz(_dec_int(ad,pm,F_COPY_LEN))
            if e<0 or off<0 or n<=0:raise ValueError("copy field")
            out.append(q41.Seg(1,n,e,off));pe,po,pl=e,off,n
    return out


def _encode_literals_into(ae,target,segs,model,pi,ts):
    pm=ar1.ProbModel(model,pi,ts);out=bytearray();pos=0
    for s in segs:
        if s.op:
            chunk=model.entries[s.e].data[s.off:s.off+s.n]
            for x in chunk:
                hist=bytes(out);pm.update(hist,x);out.append(x)
            pos+=s.n
        else:
            for x in target[pos:pos+s.n]:
                hist=bytes(out);ae.symbol(x,pm.frequencies(hist,len(out)))
                pm.update(hist,x);out.append(x)
            pos+=s.n
    if bytes(out)!=target:raise ValueError("literal traversal")


def _decode_literals_from(ad,segs,model,pi,ts):
    pm=ar1.ProbModel(model,pi,ts);out=bytearray()
    for s in segs:
        if s.op:
            chunk=model.entries[s.e].data[s.off:s.off+s.n]
            for x in chunk:
                hist=bytes(out);pm.update(hist,x);out.append(x)
        else:
            for _ in range(s.n):
                hist=bytes(out);x=ad.symbol(pm.frequencies(hist,len(out)))
                pm.update(hist,x);out.append(x)
    return bytes(out)


def pack_unified(target,path,model,ts,q41_blob=None):
    target=bytes(target);digest=hashlib.sha256(target).digest()
    if model.max_unix_ns>=ts or any(e.digest==digest for e in model.entries):raise ValueError("leakage")
    if q41_blob is None:q41_blob=q41.pack(target,path,model,ts)
    strategy,segs=ar1.q41_segments(q41_blob);flags,meta=_path_meta_encode(path,model,strategy)
    pi=ar1.path_index(path,model)
    ae=ar1.ArithmeticEncoder()
    _encode_skeleton_into(ae,segs,model,path,ts)
    _encode_literals_into(ae,target,segs,model,pi,ts)
    stream=ae.finish()
    return H.pack(MAGIC_U,VER,flags,ts,model.model_id[:16],digest)+meta+q41.uv(len(segs))+stream


def unpack_unified(blob,model):
    magic,v,flags,ts,mid,digest=H.unpack_from(blob)
    if magic!=MAGIC_U or v!=VER or mid!=model.model_id[:16] or model.max_unix_ns>=ts:raise ValueError("model/header")
    p=H.size;path,p=_path_meta_decode(blob,p,model,flags);count,p=q41.rv(blob,p)
    pi=ar1.path_index(path,model)
    ad=GenericArithmeticDecoder(blob[p:])
    segs=_decode_skeleton_from(ad,count,model,path,ts)
    target=_decode_literals_from(ad,segs,model,pi,ts)
    if hashlib.sha256(target).digest()!=digest:raise ValueError("exactness")
    return target


def pack_max(target,path,model,ts):
    q=q41.pack(target,path,model,ts)
    a1=ar1.pack_ar(target,path,model,ts,q)
    a2=pack_ar2(target,path,model,ts,q)
    au=pack_unified(target,path,model,ts,q)
    return min((q,a1,a2,au),key=lambda b:(len(b),b[:4]))


def unpack_max(blob,model):
    if blob[:4]==MAGIC_U:return unpack_unified(blob,model)
    if blob[:4]==MAGIC:return unpack_ar2(blob,model)
    if blob[:4]==ar1.MAGIC:return ar1.unpack_ar(blob,model)
    return q41.unpack(blob,model)
