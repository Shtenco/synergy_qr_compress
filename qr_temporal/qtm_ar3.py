#!/usr/bin/env python3
"""QTM-AR3: learned 2..16-byte vocabulary + temporal phrase carrier."""
from __future__ import annotations
from collections import defaultdict
import hashlib, math, struct

from . import qtd41 as q41
from . import qtm_ar as ar1
from . import qtm_ar2 as ar2

MAGIC=b"QAP3"; MAGIC_X=b"QXU3"; VER=1
H=ar2.H
H_MIN=struct.Struct(">4sB16s32s")
LENS=(2,3,4,5,6,8,12,16)
MAX_VOCAB=512


def _tw(a,t):
    age=max(0,t-a);h=age//3_600_000_000_000
    return max(1,256>>min(8,(h+1).bit_length()-1))


class Vocabulary:
    def __init__(self,model,path,ts):
        c={}
        for e in model.entries:
            if e.unix_ns>=ts:continue
            w=_tw(e.unix_ns,ts)*(3 if e.path==path else 1);d=e.data
            for L in LENS:
                step=1 if L<=6 else 2
                for i in range(0,max(0,len(d)-L+1),step):
                    p=d[i:i+L];c[p]=c.get(p,0)+w
                if len(c)>120000:
                    c=dict(sorted(c.items(),key=lambda z:(-z[1]*(len(z[0])-1),-len(z[0]),z[0]))[:60000])
        a=[(n*(len(p)-1),n,len(p),p) for p,n in c.items() if n>=2]
        a.sort(key=lambda x:(-x[0],-x[2],-x[1],x[3]));a=a[:MAX_VOCAB]
        self.p=[x[3] for x in a];self.n=[x[1] for x in a]
        self.by=defaultdict(list)
        for r,p in enumerate(self.p):self.by[p[0]].append(r)
        for b in self.by:self.by[b].sort(key=lambda r:(-len(self.p[r]),-self.n[r],r))
    def __len__(self):return len(self.p)


def _plan(v,data,segs,min_len):
    ev=[];pos=0
    for s in segs:
        if s.op:pos+=s.n;continue
        end=pos+s.n;i=pos
        while i<end:
            r=None
            for x in v.by.get(data[i],()):
                p=v.p[x]
                if len(p)>=min_len and len(p)<=end-i and data.startswith(p,i):
                    r=x;break
            if r is None:i+=1
            else:ev.append((i,r));i+=len(v.p[r])
        pos=end
    return ev


def _put_byte_model(pm,out,chunk):
    for x in chunk:
        h=bytes(out);pm.update(h,x);out.append(x)


def _encode_raw(ae,target,segs,events,model,pi,ts,v):
    pm=ar1.ProbModel(model,pi,ts);emap=dict(events);out=bytearray();pos=0
    for s in segs:
        if s.op:
            q=model.entries[s.e].data[s.off:s.off+s.n];_put_byte_model(pm,out,q);pos+=s.n;continue
        end=pos+s.n
        while pos<end:
            r=emap.get(pos)
            if r is not None:
                p=v.p[r]
                if pos+len(p)>end or target[pos:pos+len(p)]!=p:raise ValueError("phrase")
                _put_byte_model(pm,out,p);pos+=len(p)
            else:
                x=target[pos];h=bytes(out);ae.symbol(x,pm.frequencies(h,len(out)))
                pm.update(h,x);out.append(x);pos+=1
    if bytes(out)!=target:raise ValueError("traversal")


def _decode_raw(ad,segs,events,model,pi,ts,v):
    pm=ar1.ProbModel(model,pi,ts);emap=dict(events);out=bytearray();pos=0
    for s in segs:
        if s.op:
            q=model.entries[s.e].data[s.off:s.off+s.n];_put_byte_model(pm,out,q);pos+=s.n;continue
        end=pos+s.n
        while pos<end:
            r=emap.get(pos)
            if r is not None:
                p=v.p[r];_put_byte_model(pm,out,p);pos+=len(p)
            else:
                h=bytes(out);x=ad.symbol(pm.frequencies(h,len(out)));pm.update(h,x);out.append(x);pos+=1
    return bytes(out)


def _paths(m):return sorted(set(e.path for e in m.entries))


def _bits(data):return [(x>>i)&1 for x in data for i in range(7,-1,-1)]


def _b2(data):
    pad=(-len(data))%8;data=data+[0]*pad;o=bytearray()
    for i in range(0,len(data),8):
        x=0
        for b in data[i:i+8]:x=(x<<1)|b
        o.append(x)
    return bytes(o)


def _temporal_encode(bits,anchor,m,k):
    W=ar2.W_NS;C=ar2.CENTER;start=((anchor+C+1+W-1)//W)*W
    cb=math.comb(m,k).bit_length()-1;per=cb+20*k;n=(len(bits)+per-1)//per;out=[anchor];p=0
    def take(q):
        nonlocal p
        x=0
        for i in range(q):x=(x<<1)|(bits[p+i] if p+i<len(bits) else 0)
        p+=q;return x
    for b in range(n):
        rank=take(cb);combo=ar2.comb_unrank(rank,k,m);res=[take(20)-C for _ in range(k)]
        base=start+b*(m+1)*W
        out.extend(base+s*W+j for s,j in zip(combo,res))
    if any(b<=a for a,b in zip(out,out[1:])):raise ValueError("order")
    return out


def _temporal_bits(ts,m,k):
    anchor=ts[0];W=ar2.W_NS;C=ar2.CENTER;start=((anchor+C+1+W-1)//W)*W
    cb=math.comb(m,k).bit_length()-1;bits=[]
    if (len(ts)-1)%k:raise ValueError("count")
    for b in range((len(ts)-1)//k):
        base=start+b*(m+1)*W;combo=[];res=[]
        for t in ts[1+b*k:1+(b+1)*k]:
            s=(t-base+C)//W;g=base+s*W;j=t-g
            if s<0 or s>=m or j<-C or j>=C:raise ValueError("point")
            combo.append(int(s));res.append(int(j+C))
        rank=ar2.comb_rank(combo)
        for i in range(cb-1,-1,-1):bits.append((rank>>i)&1)
        for x in res:
            for i in range(19,-1,-1):bits.append((x>>i)&1)
    return bits


def _uniform_varint(ae,n):
    f=[1]*256
    for b in q41.uv(n):ae.symbol(b,f)


def _read_uniform(ad):
    f=[1]*256;o=bytearray()
    while 1:
        b=ad.symbol(f);o.append(b)
        if b<128:break
    return q41.rv(bytes(o),0)[0]


def _side(events,v):
    ae=ar1.ArithmeticEncoder();_uniform_varint(ae,len(events));prev=0
    freq=[max(1,x) for x in v.n] or [1]
    for pos,r in events:
        _uniform_varint(ae,pos-prev);ae.symbol(r,freq);prev=pos+len(v.p[r])
    return ae.finish()


def _unside(data,v):
    ad=ar2.GenericArithmeticDecoder(data);n=_read_uniform(ad);prev=0;ev=[]
    freq=[max(1,x) for x in v.n] or [1]
    for _ in range(n):
        gap=_read_uniform(ad);r=ad.symbol(freq)
        if r>=len(v):raise ValueError("rank")
        pos=prev+gap;ev.append((pos,r));prev=pos+len(v.p[r])
    return ev


def pack_temporal(target,path,model,ts,*,m=1048576,k=1,min_phrase_len=2,q41_blob=None):
    target=bytes(target);dg=hashlib.sha256(target).digest()
    if model.max_unix_ns>=ts or any(e.digest==dg for e in model.entries):raise ValueError("leakage")
    paths=_paths(model)
    if path not in paths:raise ValueError("path absent from shared model")
    if q41_blob is None:q41_blob=q41.pack(target,path,model,ts)
    _,segs=ar1.q41_segments(q41_blob);pi=ar1.path_index(path,model);v=Vocabulary(model,path,ts)
    ev=_plan(v,target,segs,min_phrase_len)
    side=q41.uv(paths.index(path))+q41.uv(len(segs))+_side(ev,v)
    ae=ar1.ArithmeticEncoder();ar2._encode_skeleton_into(ae,segs,model,path,ts);_encode_raw(ae,target,segs,ev,model,pi,ts,v)
    core=H_MIN.pack(MAGIC_X,VER,model.model_id[:16],dg)+ae.finish()
    return core,_temporal_encode(_bits(side),ts,m,k),{"events":len(ev),"covered":sum(len(v.p[r]) for _,r in ev),"side_bytes":len(side)}


def unpack_temporal(core,timestamps,model,*,m=1048576,k=1):
    magic,ver,mid,dg=H_MIN.unpack_from(core)
    if magic!=MAGIC_X or ver!=VER or mid!=model.model_id[:16]:raise ValueError("header")
    ts=timestamps[0]
    if model.max_unix_ns>=ts:raise ValueError("temporal cutoff")
    side=_b2(_temporal_bits(timestamps,m,k));p=0;pid,p=q41.rv(side,p);count,p=q41.rv(side,p)
    paths=_paths(model)
    if pid>=len(paths):raise ValueError("path")
    path=paths[pid];v=Vocabulary(model,path,ts);ev=_unside(side[p:],v);pi=ar1.path_index(path,model)
    ad=ar2.GenericArithmeticDecoder(core[H_MIN.size:]);segs=ar2._decode_skeleton_from(ad,count,model,path,ts)
    pos=0;spans=[]
    for s in segs:
        if not s.op:spans.append((pos,pos+s.n))
        pos+=s.n
    for a,r in ev:
        b=a+len(v.p[r])
        if not any(a>=x and b<=y for x,y in spans):raise ValueError("event outside literal")
    target=_decode_raw(ad,segs,ev,model,pi,ts,v)
    if hashlib.sha256(target).digest()!=dg:raise ValueError("sha")
    return target


# Byte-only phrase expert: ranks stay inside arithmetic stream.
def pack_phrase(target,path,model,ts,q41_blob=None):
    target=bytes(target);dg=hashlib.sha256(target).digest()
    if q41_blob is None:q41_blob=q41.pack(target,path,model,ts)
    st,segs=ar1.q41_segments(q41_blob);pi=ar1.path_index(path,model);v=Vocabulary(model,path,ts)
    ev=_plan(v,target,segs,6)
    flags,meta=ar2._path_meta_encode(path,model,st)
    ae=ar1.ArithmeticEncoder();ar2._encode_skeleton_into(ae,segs,model,path,ts)
    _uniform_varint(ae,len(ev));prev=0;freq=[max(1,x) for x in v.n] or [1]
    for pos,r in ev:
        _uniform_varint(ae,pos-prev);ae.symbol(r,freq);prev=pos+len(v.p[r])
    _encode_raw(ae,target,segs,ev,model,pi,ts,v)
    return H.pack(MAGIC,VER,flags,ts,model.model_id[:16],dg)+meta+q41.uv(len(segs))+ae.finish()


def unpack_phrase(blob,model):
    magic,ver,flags,ts,mid,dg=H.unpack_from(blob)
    if magic!=MAGIC or ver!=VER or mid!=model.model_id[:16] or model.max_unix_ns>=ts:raise ValueError("header")
    p=H.size;path,p=ar2._path_meta_decode(blob,p,model,flags);count,p=q41.rv(blob,p)
    v=Vocabulary(model,path,ts);pi=ar1.path_index(path,model);ad=ar2.GenericArithmeticDecoder(blob[p:])
    segs=ar2._decode_skeleton_from(ad,count,model,path,ts);n=_read_uniform(ad);freq=[max(1,x) for x in v.n] or [1]
    ev=[];prev=0
    for _ in range(n):
        gap=_read_uniform(ad);r=ad.symbol(freq);pos=prev+gap;ev.append((pos,r));prev=pos+len(v.p[r])
    target=_decode_raw(ad,segs,ev,model,pi,ts,v)
    if hashlib.sha256(target).digest()!=dg:raise ValueError("sha")
    return target


def pack_max(target,path,model,ts):
    q=q41.pack(target,path,model,ts)
    a1=ar1.pack_ar(target,path,model,ts,q)
    a2=ar2.pack_unified(target,path,model,ts,q)
    a3=pack_phrase(target,path,model,ts,q)
    return min((q,a1,a2,a3),key=lambda b:(len(b),b[:4]))


def unpack_max(blob,model):
    if blob[:4]==MAGIC:return unpack_phrase(blob,model)
    if blob[:4]==ar1.MAGIC:return ar1.unpack_ar(blob,model)
    if blob[:4]==ar2.MAGIC_U:return ar2.unpack_unified(blob,model)
    return q41.unpack(blob,model)
