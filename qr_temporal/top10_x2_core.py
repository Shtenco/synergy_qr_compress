#!/usr/bin/env python3
"""Top-10 X2 common core: compact exact container + TEXT-TABLE + adaptive Segment-MDL + SPEED profile."""
from __future__ import annotations
import math,re,struct,zlib
import brotli
try:
    import lz4.block as _lz4_block
except Exception:
    _lz4_block=None

from . import fusion_v5_x2 as base

MAGIC=b"X2";VER=1
M_TABLE=100;M_SEG=101;M_LZ4=102
NUM_RE=re.compile(rb'[-+]?(?:\d+\.\d+|\d+)(?:[eE][-+]?\d+)?')

def vi(x:int)->bytes:return base.vi(x)
def vu(b:bytes,p=0):return base.vu(b,p)
def zz(x:int)->int:return 2*abs(x)-(1 if x<0 else 0)
def unzz(x:int)->int:return -(x//2+1) if x&1 else x//2

def _series_encode(vals):
    opts=[];n=len(vals)
    for order in range(5):
        seq=list(vals)
        for j in range(order):
            for i in range(n-1,j,-1):seq[i]-=seq[i-1]
        o=bytearray([order]);o+=vi(n)
        for q in seq:o+=vi(zz(q))
        opts.append(bytes(o))
    return min(opts,key=len)

def _series_decode(raw,p):
    order=raw[p];p+=1
    if order>4:raise ValueError("series order")
    cnt,p=vu(raw,p);seq=[]
    for _ in range(cnt):
        q,p=vu(raw,p);seq.append(unzz(q))
    for j in range(order-1,-1,-1):
        for i in range(j+1,cnt):seq[i]+=seq[i-1]
    return seq,p

def _variable_decimal(tokens):
    vals=[];fracs=[]
    for t in tokens:
        m=re.fullmatch(rb'(-?)(\d+)\.(\d+)',t)
        if not m:return None
        a=m.group(2);b=m.group(3)
        if a.startswith(b"0") and len(a)>1:return None
        f=len(b)
        if f>18:return None
        x=int(a)*(10**f)+int(b)
        if m.group(1):x=-x
        vals.append(x);fracs.append(f)
    mf=max(fracs,default=0);scaled=[x*(10**(mf-f)) for x,f in zip(vals,fracs)]
    for t,x,f in zip(tokens,scaled,fracs):
        q=x//(10**(mf-f));av=abs(q);scale=10**f
        r=(b"-" if q<0 else b"")+str(av//scale).encode()+b"."+str(av%scale).zfill(f).encode()
        if r!=t:return None
    return mf,fracs,scaled

def _wrap(mode,source,tail):
    return MAGIC+bytes([VER,mode])+vi(len(source))+struct.pack(">I",zlib.crc32(source)&0xffffffff)+tail

def _parse(blob):
    if blob[:2]!=MAGIC or blob[2]!=VER:raise ValueError("X2 header")
    mode=blob[3];n,p=vu(blob,4)
    if p+4>len(blob):raise ValueError("X2 truncated")
    crc=struct.unpack(">I",blob[p:p+4])[0];p+=4
    return mode,n,crc,p

def _strip_v4(blob):
    mode=blob[4];_,p=base.vu(blob,5);p+=32
    return mode,blob[p:]

def _native_candidates(d:bytes,quality=11,full=True):
    out=[]
    for b,label in base.v4_candidates(d,quality):
        mode,tail=_strip_v4(b)
        if not full and mode not in (base.RAW,base.BR,base.D8_BR,base.SH2_D8_BR,base.SH16_D8_BR,
                                     base.RLE_ZSTD,base.PERIOD_RAW,base.PERIOD_BR,base.SPARSE_STRIDE,base.BZ2):
            continue
        out.append((mode,tail,label))
    return out

def _decode_native(mode,n,tail):
    if mode==base.RAW:o=tail
    elif mode==base.BR:o=brotli.decompress(tail)
    elif mode==base.D8_BR:o=base.undelta8(brotli.decompress(tail))
    elif mode==base.SH2_D8_BR:o=base.unshuffle(base.undelta8(brotli.decompress(tail)),2)
    elif mode==base.SH16_D8_BR:o=base.unshuffle(base.undelta8(brotli.decompress(tail)),16)
    elif mode==base.SH16_D8D8_BR:o=base.unshuffle(base.undelta8(base.undelta8(brotli.decompress(tail))),16)
    elif mode==base.RLE_ZSTD:o=base.unrle(base.zstd_decompress(tail,n))
    elif mode==base.PERIOD_RAW:
        k,p=vu(tail,0);pat=tail[p:p+k];o=(pat*((n+k-1)//k))[:n]
    elif mode==base.PERIOD_BR:
        k,p=vu(tail,0);pat=brotli.decompress(tail[p:]);o=(pat*((n+k-1)//k))[:n]
    elif mode==base.SPARSE_STRIDE:
        first,p=vu(tail,0);stride,p=vu(tail,p);vals=tail[p:];a=bytearray(n);pos=first
        for x in vals:
            if pos>=n:raise ValueError("sparse overflow")
            a[pos]=x;pos+=stride
        o=bytes(a)
    elif mode==base.GRAD_BR:
        w,p=vu(tail,0);o=base.gradient_decode(brotli.decompress(tail[p:]),w)
    elif mode==base.BZ2:
        import bz2;o=bz2.decompress(tail)
    else:raise ValueError("X2 native mode")
    if len(o)!=n:raise ValueError("X2 native len")
    return o

def _canonical_int(tokens):
    vals=[]
    for t in tokens:
        try:x=int(t)
        except Exception:return None
        if str(x).encode()!=t:return None
        vals.append(x)
    return vals

def _canonical_fixed(tokens):
    vals=[];frac=None
    for t in tokens:
        m=re.fullmatch(rb'(-?)(\d+)\.(\d+)',t)
        if not m:return None
        a=m.group(2);b=m.group(3)
        if a.startswith(b"0") and len(a)>1:return None
        f=len(b)
        if frac is None:frac=f
        if f!=frac:return None
        x=int(a)*(10**f)+int(b)
        if m.group(1):x=-x
        av=abs(x);r=(b"-" if x<0 else b"")+str(av//10**f).encode()+b"."+str(av%10**f).zfill(f).encode()
        if r!=t:return None
        vals.append(x)
    return frac,vals

def table_normalize(data:bytes):
    lines=data.splitlines(keepends=True)
    if len(lines)<4:return None
    shapes=[];ids={};rowids=[];fields=[]
    for line in lines:
        lits=[];nums=[];p=0
        for m in NUM_RE.finditer(line):
            lits.append(line[p:m.start()]);nums.append(m.group());p=m.end()
        lits.append(line[p:]);key=tuple(lits);sid=ids.get(key)
        if sid is None:
            if len(shapes)>=128:return None
            sid=len(shapes);ids[key]=sid;shapes.append(key);fields.append([[] for _ in nums])
        if len(fields[sid])!=len(nums):return None
        rowids.append(sid)
        for j,t in enumerate(nums):fields[sid][j].append(t)
    if not any(fields):return None
    o=bytearray();o+=vi(len(lines))+vi(len(shapes))+vi(len(rowids))
    for sid in rowids:o+=vi(sid)
    for sid,key in enumerate(shapes):
        o+=vi(len(key)-1)
        for lit in key:o+=vi(len(lit))+lit
        for toks in fields[sid]:
            ints=_canonical_int(toks)
            if ints is not None:
                o.append(0);o+=_series_encode(ints);continue
            fx=_canonical_fixed(toks)
            if fx is not None:
                frac,vals=fx;o.append(1);o+=vi(frac)+_series_encode(vals);continue
            vd=_variable_decimal(toks)
            if vd is not None:
                mf,fracs,vals=vd;o.append(3);o+=vi(mf)+_series_encode(vals)
                for f in fracs:o+=vi(f)
                continue
            o.append(2);o+=vi(len(toks))
            for t in toks:o+=vi(len(t))+t
    return bytes(o)

def table_denormalize(raw:bytes):
    p=0;nlines,p=vu(raw,p);nsh,p=vu(raw,p);nr,p=vu(raw,p)
    if nr!=nlines:raise ValueError("table rows")
    rowids=[]
    for _ in range(nr):x,p=vu(raw,p);rowids.append(x)
    shapes=[];fieldvals=[]
    for sid in range(nsh):
        nf,p=vu(raw,p);lits=[]
        for _ in range(nf+1):n,p=vu(raw,p);lits.append(raw[p:p+n]);p+=n
        fs=[]
        for _ in range(nf):
            typ=raw[p];p+=1
            if typ==0:
                xs,p=_series_decode(raw,p);vals=[str(x).encode() for x in xs]
            elif typ==1:
                frac,p=vu(raw,p);xs,p=_series_decode(raw,p);vals=[];scale=10**frac
                for x in xs:
                    av=abs(x);vals.append((b"-" if x<0 else b"")+str(av//scale).encode()+b"."+str(av%scale).zfill(frac).encode())
            elif typ==3:
                mf,p=vu(raw,p);xs,p=_series_decode(raw,p);fracs=[]
                for _ in range(len(xs)):f,p=vu(raw,p);fracs.append(f)
                vals=[]
                for x,f in zip(xs,fracs):
                    q=x//(10**(mf-f));av=abs(q);scale=10**f
                    vals.append((b"-" if q<0 else b"")+str(av//scale).encode()+b"."+str(av%scale).zfill(f).encode())
            elif typ==2:
                cnt,p=vu(raw,p);vals=[]
                for _ in range(cnt):n,p=vu(raw,p);vals.append(raw[p:p+n]);p+=n
            else:raise ValueError("table field type")
            fs.append(vals)
        shapes.append(lits);fieldvals.append(fs)
    if p!=len(raw):raise ValueError("table trailing")
    curs=[[0]*len(fs) for fs in fieldvals];out=bytearray()
    for sid in rowids:
        if sid>=nsh:raise ValueError("table sid")
        lits=shapes[sid];fs=fieldvals[sid];out+=lits[0]
        for j,vals in enumerate(fs):
            k=curs[sid][j]
            if k>=len(vals):raise ValueError("table field count")
            out+=vals[k]+lits[j+1];curs[sid][j]+=1
    return bytes(out)

def _table_candidate(d,quality=11):
    raw=table_normalize(d)
    if raw is None:return None
    return M_TABLE,brotli.compress(raw,quality=quality),"text-table"

def _features(x):
    n=max(1,len(x));cnt=[0]*256
    for b in x:cnt[b]+=1
    ent=-sum((c/n)*math.log2(c/n) for c in cnt if c)
    if len(x)>1:
        c2=[0]*256;prev=x[0]
        for b in x[1:]:c2[(b-prev)&255]+=1;prev=b
        nn=len(x)-1;entd=-sum((c/nn)*math.log2(c/nn) for c in c2 if c)
    else:entd=0
    return (sum((9<=b<=13 or 32<=b<127) for b in x)/n,x.count(0)/n,
            5*sum(48<=b<=57 for b in x)/n,20*x.count(10)/n,10*x.count(44)/n,
            10*(x.count(123)+x.count(125)+x.count(91)+x.count(93))/n,
            10*x.count(58)/n,ent,entd)

def adaptive_boundaries(data,W=512,threshold=1.0):
    if len(data)<4*W:return [0,len(data)]
    fs=[_features(data[i:i+W]) for i in range(0,len(data),W)]
    ds=[0.0]+[sum(abs(a-b) for a,b in zip(fs[i],fs[i-1])) for i in range(1,len(fs))]
    cuts=[]
    for i in range(1,len(ds)-1):
        if ds[i]>=threshold and ds[i]>=ds[i-1] and ds[i]>=ds[i+1]:cuts.append(i*W)
    if len(cuts)>12:return [0,len(data)]
    return [0]+cuts+[len(data)]

def _refine_boundaries(data,cuts):
    if len(cuts)<=2:return cuts
    refined=[0]
    for c in cuts[1:-1]:
        lo=max(refined[-1]+512,c-512);hi=min(len(data)-512,c+512);best=(0.0,c)
        for p in range(lo,hi+1,64):
            if p<256 or p+256>len(data):continue
            a=_features(data[p-256:p]);b=_features(data[p:p+256]);score=sum(abs(x-y) for x,y in zip(a,b))
            if score>best[0]:best=(score,p)
        if best[1]-refined[-1]>=512:refined.append(best[1])
    if len(data)-refined[-1]<512 and len(refined)>1:refined.pop()
    refined.append(len(data));return refined

def _segment_best(d,quality=11,full=True):
    opts=_native_candidates(d,quality,full);tc=_table_candidate(d,quality)
    if tc:opts.append(tc)
    return min(opts,key=lambda x:(len(x[1])+1,x[2]))

def _segment_payload(data,quality=11,full=True):
    variants=[]
    for th in (0.75,1.0,1.5,2.0):
        cuts=_refine_boundaries(data,adaptive_boundaries(data,512,th))
        if len(cuts)<=2:continue
        o=bytearray();o+=vi(len(cuts)-1)
        for a,b in zip(cuts,cuts[1:]):
            d=data[a:b];mode,pay,_=_segment_best(d,quality,full);o+=vi(len(d))+bytes([mode])+vi(len(pay))+pay
        variants.append(bytes(o))
    return min(variants,key=len) if variants else None

def _decode_segment(payload):
    p=0;cnt,p=vu(payload,p);out=bytearray()
    for _ in range(cnt):
        n,p=vu(payload,p);mode=payload[p];p+=1;ln,p=vu(payload,p);tail=payload[p:p+ln];p+=ln
        d=table_denormalize(brotli.decompress(tail)) if mode==M_TABLE else _decode_native(mode,n,tail)
        if len(d)!=n:raise ValueError("segment n")
        out+=d
    if p!=len(payload):raise ValueError("segment trailing")
    return bytes(out)

def compress_whole(data:bytes,quality=11,full=True):
    d=bytes(data);opts=[]
    for mode,tail,label in _native_candidates(d,quality,full):opts.append((_wrap(mode,d,tail),label))
    tc=_table_candidate(d,quality)
    if tc:opts.append((_wrap(tc[0],d,tc[1]),tc[2]))
    return min(opts,key=lambda x:(len(x[0]),x[1]))[0]

def compress_max(data:bytes):
    d=bytes(data);opts=[(compress_whole(d,11,True),"whole")];sp=_segment_payload(d,11,True)
    if sp is not None:opts.append((_wrap(M_SEG,d,sp),"segment"))
    return min(opts,key=lambda x:(len(x[0]),x[1]))[0]

def _sample_stats(d):
    step=max(1,len(d)//4096);s=d[::step][:4096];n=max(1,len(s))
    return (sum((9<=b<=13 or 32<=b<127) for b in s)/n,sum(48<=b<=57 for b in s)/n,len(set(s)),d.count(0)/max(1,len(d)))

def compress_speed(data:bytes):
    d=bytes(data);n=len(d);best=_wrap(base.RAW,d,d);ascii_ratio,digit,uniq,zero=_sample_stats(d)
    if zero>.90:
        ss=base.sparse_stride(d)
        if ss:
            first,stride,vals=ss;a=_wrap(base.SPARSE_STRIDE,d,vi(first)+vi(stride)+vals)
            if len(a)<len(best):best=a
            return best
    if ascii_ratio>.92:
        if digit>.10 and d.count(b"\n")>=4:
            tc=_table_candidate(d,4)
            if tc:
                a=_wrap(M_TABLE,d,tc[1])
                if len(a)<len(best):best=a
        a=_wrap(base.BR,d,brotli.compress(d,quality=4))
        return a if len(a)<len(best) else best
    if zero>.45 and n%16==0:
        ss=base.sparse_stride(d)
        if ss:
            first,stride,vals=ss;a=_wrap(base.SPARSE_STRIDE,d,vi(first)+vi(stride)+vals)
        else:
            x=base.delta8(base.delta8(base.shuffle(d,16)));a=_wrap(base.SH16_D8D8_BR,d,brotli.compress(x,quality=4))
        return a if len(a)<len(best) else best
    probe=d[:4096];dz=zlib.compress(base.delta8(probe),1);rz=zlib.compress(probe,1)
    if len(dz)*4<len(rz)*3:
        x=base.delta8(d);a=_wrap(base.D8_BR,d,brotli.compress(x,quality=4));return a if len(a)<len(best) else best
    a=_wrap(base.BR,d,brotli.compress(d,quality=4));return a if len(a)<len(best) else best

def compress_balanced(data:bytes):
    d=bytes(data);a=compress_speed(d)
    if len(a)<=max(96,int(len(d)*0.08)):return a
    b=compress_whole(d,9,True);return b if len(b)<len(a) else a

def compress_turbo_score(data:bytes):
    """Maximum ratio/ms profile: native LZ4-block candidate plus RAW floor."""
    d=bytes(data);raw=_wrap(base.RAW,d,d)
    if _lz4_block is None:
        return raw
    pay=_lz4_block.compress(d,mode="fast",acceleration=2,store_size=False);a=_wrap(M_LZ4,d,pay)
    return a if len(a)<len(raw) else raw

def decompress(blob:bytes):
    mode,n,crc,p=_parse(blob);tail=blob[p:]
    if mode==M_TABLE:o=table_denormalize(brotli.decompress(tail))
    elif mode==M_SEG:o=_decode_segment(tail)
    elif mode==M_LZ4:
        if _lz4_block is None:raise RuntimeError("lz4 is required to decode X2 TURBO archives")
        o=_lz4_block.decompress(tail,uncompressed_size=n)
    else:o=_decode_native(mode,n,tail)
    if len(o)!=n or (zlib.crc32(o)&0xffffffff)!=crc:raise ValueError("X2 CRC/length")
    return o

def inspect(blob):
    mode,n,crc,_=_parse(blob)
    return {"mode":mode,"original_bytes":n,"archive_bytes":len(blob),"ratio":n/len(blob),"crc32":f"{crc:08x}"}
