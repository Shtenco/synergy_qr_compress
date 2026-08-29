#!/usr/bin/env python3
"""
Fusion V5-X2 — exact non-regressing compression experiment.

Candidate families:
  * legacy Fusion-V4 compatible whole-file routes;
  * compact segment-MDL with one outer SHA-256;
  * exact zlib-stream semantic normalization (PDF-oriented, generic byte scan);
  * conditional second-stage recompression.

Every V5-native candidate is byte-for-byte verified before admission.
"""
from __future__ import annotations
import bz2, hashlib, lzma, math, struct, subprocess, zlib
import brotli

MAGIC4=b"QV4"; V4VER=1
MAGIC5=b"QV5"; V5VER=1
MODE_SEG=1
MODE_SEG_BR=2
MODE_FORMAT=3
MODE_FORMAT_BR=4

def vi(x:int)->bytes:
    if x<0: raise ValueError("negative")
    o=bytearray()
    while True:
        b=x&127; x>>=7
        if x:o.append(b|128)
        else:o.append(b);return bytes(o)

def vu(b:bytes,p:int=0):
    x=s=0
    for _ in range(10):
        if p>=len(b): raise ValueError("truncated varint")
        q=b[p];p+=1;x|=(q&127)<<s
        if not q&128:return x,p
        s+=7
    raise ValueError("varint too large")

def delta8(d:bytes)->bytes:
    o=bytearray(len(d));p=0
    for i,x in enumerate(d):o[i]=(x-p)&255;p=x
    return bytes(o)

def undelta8(d:bytes)->bytes:
    o=bytearray(len(d));p=0
    for i,x in enumerate(d):p=(p+x)&255;o[i]=p
    return bytes(o)

def shuffle(d:bytes,w:int)->bytes:
    if len(d)%w: raise ValueError("unaligned")
    return b"".join(d[j::w] for j in range(w))

def unshuffle(d:bytes,w:int)->bytes:
    if len(d)%w: raise ValueError("unaligned")
    n=len(d)//w;o=bytearray(len(d));p=0
    for j in range(w):
        lane=d[p:p+n];p+=n
        for i,x in enumerate(lane):o[i*w+j]=x
    return bytes(o)

def rle(d:bytes)->bytes:
    o=bytearray();i=0
    while i<len(d):
        j=i+1
        while j<len(d) and d[j]==d[i]:j+=1
        o+=vi(j-i)+bytes([d[i]]);i=j
    return bytes(o)

def unrle(d:bytes)->bytes:
    o=bytearray();p=0
    while p<len(d):
        n,p=vu(d,p)
        if p>=len(d):raise ValueError("rle")
        o+=bytes([d[p]])*n;p+=1
    return bytes(o)

def period(d:bytes,max_period=32768):
    n=len(d)
    if n<2:return None
    pi=[0]*n;j=0
    for i in range(1,n):
        while j and d[i]!=d[j]:j=pi[j-1]
        if d[i]==d[j]:j+=1
        pi[i]=j
    p=n-pi[-1]
    if 0<p<n and p<=max_period and all(d[i]==d[i%p] for i in range(p,n)):return d[:p]
    return None

def sparse_stride(d:bytes):
    pos=[i for i,x in enumerate(d) if x]
    if len(pos)<2:return None
    stride=pos[1]-pos[0]
    if stride<=0 or any(b-a!=stride for a,b in zip(pos,pos[1:])):return None
    return pos[0],stride,bytes(d[i] for i in pos)

def gradient_encode(d:bytes,w:int)->bytes:
    o=bytearray(len(d))
    for i,x in enumerate(d):
        l=d[i-1] if i%w else 0;u=d[i-w] if i>=w else 0;ul=d[i-w-1] if i>=w and i%w else 0
        o[i]=(x-(l+u-ul))&255
    return bytes(o)

def gradient_decode(r:bytes,w:int)->bytes:
    o=bytearray(len(r))
    for i,x in enumerate(r):
        l=o[i-1] if i%w else 0;u=o[i-w] if i>=w else 0;ul=o[i-w-1] if i>=w and i%w else 0
        o[i]=(x+l+u-ul)&255
    return bytes(o)

def zstd_compress(d:bytes,level=19)->bytes:
    try:
        import zstandard as zstd
        return zstd.ZstdCompressor(level=level,write_checksum=False,write_content_size=True,write_dict_id=False).compress(d)
    except Exception:
        return subprocess.run(["zstd","-q",f"-{level}","-c"],input=d,stdout=subprocess.PIPE,check=True).stdout

def zstd_decompress(d:bytes,expected=0)->bytes:
    try:
        import zstandard as zstd
        return zstd.ZstdDecompressor().decompress(d,max_output_size=max(expected,1) if expected else 0)
    except Exception:
        return subprocess.run(["zstd","-q","-d","-c"],input=d,stdout=subprocess.PIPE,check=True).stdout

RAW=0;BR=1;D8_BR=2;SH2_D8_BR=3;SH16_D8_BR=4;RLE_ZSTD=5;PERIOD_RAW=6;BZ2=7
SH16_D8D8_BR=8;SPARSE_STRIDE=9;PERIOD_BR=10;GRAD_BR=11

def _v4wrap(mode,source,payload,extra=b""):
    return MAGIC4+bytes([V4VER,mode])+vi(len(source))+hashlib.sha256(source).digest()+extra+payload

def v4_candidates(data:bytes,quality=11):
    c=[(_v4wrap(RAW,data,data),"raw")]
    def br(mode,x,label,extra=b""):
        c.append((_v4wrap(mode,data,brotli.compress(x,quality=quality),extra),label))
    br(BR,data,"br")
    br(D8_BR,delta8(data),"d8")
    if len(data)%2==0:br(SH2_D8_BR,delta8(shuffle(data,2)),"sh2d")
    if len(data)%16==0:
        s=shuffle(data,16);br(SH16_D8_BR,delta8(s),"sh16d");br(SH16_D8D8_BR,delta8(delta8(s)),"sh16d2")
    if data and data.count(0)>len(data)//2:
        c.append((_v4wrap(RLE_ZSTD,data,zstd_compress(rle(data),19)),"rle"))
    p=period(data)
    if p is not None:
        c.append((_v4wrap(PERIOD_RAW,data,vi(len(p))+p),"periodraw"))
        c.append((_v4wrap(PERIOD_BR,data,brotli.compress(p,quality=quality),vi(len(p))),"periodbr"))
    ss=sparse_stride(data)
    if ss:
        first,stride,vals=ss;c.append((_v4wrap(SPARSE_STRIDE,data,vals,vi(first)+vi(stride)),"sparse"))
    if len(data)>=256:
        root=max(2,int(math.sqrt(len(data))))
        widths=sorted(set([root+d for d in range(-4,5) if root+d>=2]+[32,64,128,256,512,1024]))
        screened=[]
        for w in widths:
            if w<len(data):
                r=gradient_encode(data,w);screened.append((len(zlib.compress(r,1)),w,r))
        for _,w,r in sorted(screened)[:2]:
            c.append((_v4wrap(GRAD_BR,data,brotli.compress(r,quality=quality),vi(w)),"grad"))
    c.append((_v4wrap(BZ2,data,bz2.compress(data,9)),"bz2"))
    return c

def v4_decompress(blob:bytes)->bytes:
    if blob[:3]!=MAGIC4 or blob[3]!=V4VER:raise ValueError("not v4")
    mode=blob[4];n,p=vu(blob,5);dg=blob[p:p+32];p+=32
    if mode==RAW:o=blob[p:]
    elif mode==BR:o=brotli.decompress(blob[p:])
    elif mode==D8_BR:o=undelta8(brotli.decompress(blob[p:]))
    elif mode==SH2_D8_BR:o=unshuffle(undelta8(brotli.decompress(blob[p:])),2)
    elif mode==SH16_D8_BR:o=unshuffle(undelta8(brotli.decompress(blob[p:])),16)
    elif mode==SH16_D8D8_BR:o=unshuffle(undelta8(undelta8(brotli.decompress(blob[p:]))),16)
    elif mode==RLE_ZSTD:o=unrle(zstd_decompress(blob[p:],n))
    elif mode==PERIOD_RAW:
        k,q=vu(blob,p);pat=blob[q:q+k];o=(pat*((n+k-1)//k))[:n]
    elif mode==PERIOD_BR:
        k,q=vu(blob,p);pat=brotli.decompress(blob[q:]);o=(pat*((n+k-1)//k))[:n]
    elif mode==SPARSE_STRIDE:
        first,q=vu(blob,p);stride,q=vu(blob,q);vals=blob[q:];a=bytearray(n);pos=first
        for x in vals:
            if pos>=n:raise ValueError("sparse")
            a[pos]=x
            pos+=stride
        o=bytes(a)
    elif mode==GRAD_BR:
        w,q=vu(blob,p);o=gradient_decode(brotli.decompress(blob[q:]),w)
    elif mode==BZ2:o=bz2.decompress(blob[p:])
    else:raise ValueError("v4 mode")
    if len(o)!=n or hashlib.sha256(o).digest()!=dg:raise ValueError("v4 integrity")
    return o

S_RAW=0;S_BR=1;S_D8_BR=2;S_SH2=3;S_SH4=4;S_SH8=5;S_SH16=6;S_SH32=7
S_SH2_D2=8;S_SH4_D2=9;S_SH8_D2=10;S_SH16_D2=11;S_SH32_D2=12
S_ZLIB=13;S_ZSTD=14;S_BZ2=15;S_GRAD=16

def _seg_record(mode:int,n:int,payload:bytes,param:int=0)->bytes:
    return bytes([mode])+vi(n)+vi(param)+vi(len(payload))+payload

def _seg_candidates(d:bytes):
    out=[(_seg_record(S_RAW,len(d),d),"raw")]
    def add(mode,payload,label,param=0):
        out.append((_seg_record(mode,len(d),payload,param),label))
    add(S_BR,brotli.compress(d,quality=11),"br")
    add(S_ZLIB,zlib.compress(d,9),"zlib")
    try:add(S_ZSTD,zstd_compress(d,19),"zstd")
    except Exception:pass
    probes=[]
    probes.append((len(zlib.compress(delta8(d),1)),S_D8_BR,delta8(d),0,"d8"))
    for w,mode1,mode2 in [(2,S_SH2,S_SH2_D2),(4,S_SH4,S_SH4_D2),(8,S_SH8,S_SH8_D2),(16,S_SH16,S_SH16_D2),(32,S_SH32,S_SH32_D2)]:
        if len(d)%w==0:
            x=shuffle(d,w);a=delta8(x);b=delta8(a)
            probes.append((len(zlib.compress(a,1)),mode1,a,0,f"sh{w}"))
            probes.append((len(zlib.compress(b,1)),mode2,b,0,f"sh{w}d2"))
    if len(d)>=256:
        for w in (16,32,64,128,256):
            if w<len(d):
                r=gradient_encode(d,w);probes.append((len(zlib.compress(r,1)),S_GRAD,r,w,f"grad{w}"))
    for _,mode,x,param,label in sorted(probes,key=lambda z:(z[0],z[4]))[:2]:
        add(mode,brotli.compress(x,quality=11),label,param)
    return out

def _decode_seg(rec:bytes,p:int):
    if p>=len(rec):raise ValueError("segment eof")
    mode=rec[p];p+=1;n,p=vu(rec,p);param,p=vu(rec,p);ln,p=vu(rec,p)
    if p+ln>len(rec):raise ValueError("segment truncated")
    q=rec[p:p+ln];p+=ln
    if mode==S_RAW:o=q
    elif mode==S_BR:o=brotli.decompress(q)
    elif mode==S_D8_BR:o=undelta8(brotli.decompress(q))
    elif mode in (S_SH2,S_SH4,S_SH8,S_SH16,S_SH32,S_SH2_D2,S_SH4_D2,S_SH8_D2,S_SH16_D2,S_SH32_D2):
        widths={S_SH2:2,S_SH4:4,S_SH8:8,S_SH16:16,S_SH32:32,S_SH2_D2:2,S_SH4_D2:4,S_SH8_D2:8,S_SH16_D2:16,S_SH32_D2:32}
        x=brotli.decompress(q)
        if mode in (S_SH2_D2,S_SH4_D2,S_SH8_D2,S_SH16_D2,S_SH32_D2):x=undelta8(undelta8(x))
        else:x=undelta8(x)
        o=unshuffle(x,widths[mode])
    elif mode==S_ZLIB:o=zlib.decompress(q)
    elif mode==S_ZSTD:o=zstd_decompress(q,n)
    elif mode==S_BZ2:o=bz2.decompress(q)
    elif mode==S_GRAD:o=gradient_decode(brotli.decompress(q),param)
    else:raise ValueError("segment mode")
    if len(o)!=n:raise ValueError("segment length")
    return o,p

def _build_segment_stream(data:bytes,bs:int)->bytes:
    recs=[]
    for p in range(0,len(data),bs):
        d=data[p:p+bs];best=min(_seg_candidates(d),key=lambda z:(len(z[0]),z[1]))[0];recs.append(best)
    return vi(bs)+vi(len(recs))+b"".join(recs)

def _decode_segment_stream(payload:bytes)->bytes:
    bs,p=vu(payload,0);count,p=vu(payload,p);o=bytearray()
    for _ in range(count):
        d,p=_decode_seg(payload,p);o+=d
    if p!=len(payload):raise ValueError("segment trailing")
    return bytes(o)

def _wrap5(mode:int,source:bytes,payload:bytes)->bytes:
    return MAGIC5+bytes([V5VER,mode])+vi(len(source))+hashlib.sha256(source).digest()+payload

F_LITERAL=0;F_ZLIB=1

def _find_next_stream(data:bytes,start:int):
    a=data.find(b"stream\n",start);b=data.find(b"stream\r\n",start)
    vals=[x for x in (a,b) if x>=0]
    if not vals:return None
    s=min(vals);marker=b"stream\r\n" if data.startswith(b"stream\r\n",s) else b"stream\n"
    return s,s+len(marker)

def _exact_zlib_level(comp:bytes):
    try:plain=zlib.decompress(comp)
    except Exception:return None
    for lv in range(1,10):
        try:
            if zlib.compress(plain,lv)==comp:return lv,plain
        except Exception:pass
    return None

def normalize_zlib_streams(data:bytes):
    out=bytearray();pos=0;search=0;replaced=0;plain_total=0
    def lit(x:bytes):
        if x:out.append(F_LITERAL);out.extend(vi(len(x)));out.extend(x)
    while True:
        hit=_find_next_stream(data,search)
        if hit is None:break
        s,ps=hit;e=data.find(b"endstream",ps)
        if e<0:break
        candidates=[e]
        if e>=1 and data[e-1:e]==b"\n":candidates.append(e-1)
        if e>=2 and data[e-2:e]==b"\r\n":candidates.append(e-2)
        best=None
        for ce in candidates:
            z=_exact_zlib_level(data[ps:ce])
            if z is not None:
                best=(ce,z[0],z[1]);break
        if best is None:
            search=ps;continue
        ce,lv,plain=best
        lit(data[pos:ps]);out.append(F_ZLIB);out.append(lv);out.extend(vi(len(plain)));out.extend(plain)
        pos=ce;search=e+9;replaced+=1;plain_total+=len(plain)
    lit(data[pos:])
    if replaced==0:return None
    return bytes(out),replaced,plain_total

def denormalize_zlib_streams(tokens:bytes)->bytes:
    out=bytearray();p=0
    while p<len(tokens):
        kind=tokens[p];p+=1
        if kind==F_LITERAL:
            n,p=vu(tokens,p)
            if p+n>len(tokens):raise ValueError("fmt literal")
            out+=tokens[p:p+n];p+=n
        elif kind==F_ZLIB:
            if p>=len(tokens):raise ValueError("fmt level")
            lv=tokens[p];p+=1;n,p=vu(tokens,p)
            if p+n>len(tokens):raise ValueError("fmt plain")
            plain=tokens[p:p+n];p+=n;out+=zlib.compress(plain,lv)
        else:raise ValueError("fmt token")
    return bytes(out)

def _format_candidate(data:bytes):
    norm=normalize_zlib_streams(data)
    if norm is None:return []
    tokens,replaced,plain_total=norm;c=[]
    backends=[(0,lzma.compress(tokens,format=lzma.FORMAT_XZ,preset=9|lzma.PRESET_EXTREME)),(1,brotli.compress(tokens,quality=11))]
    try:backends.append((2,zstd_compress(tokens,19)))
    except Exception:pass
    for backend,payload in backends:
        body=bytes([backend])+vi(replaced)+vi(plain_total)+payload
        c.append((_wrap5(MODE_FORMAT,data,body),f"format-{backend}"))
        br=brotli.compress(body,quality=11)
        if len(br)+1<len(body):c.append((_wrap5(MODE_FORMAT_BR,data,bytes([backend])+br),f"format-{backend}+br"))
    return c

def _decode_format(mode:int,payload:bytes)->bytes:
    if mode==MODE_FORMAT_BR:
        if not payload:raise ValueError("fmt backend")
        backend=payload[0];body=brotli.decompress(payload[1:])
        if not body or body[0]!=backend:raise ValueError("fmt backend mismatch")
    else:
        body=payload;backend=body[0]
    p=1;_,p=vu(body,p);_,p=vu(body,p);comp=body[p:]
    if backend==0:tokens=lzma.decompress(comp)
    elif backend==1:tokens=brotli.decompress(comp)
    elif backend==2:tokens=zstd_decompress(comp)
    else:raise ValueError("fmt backend")
    return denormalize_zlib_streams(tokens)

def _v5_decompress(blob:bytes)->bytes:
    if blob[:3]!=MAGIC5 or blob[3]!=V5VER:raise ValueError("not v5")
    mode=blob[4];n,p=vu(blob,5);dg=blob[p:p+32];p+=32;payload=blob[p:]
    if mode==MODE_SEG:o=_decode_segment_stream(payload)
    elif mode==MODE_SEG_BR:o=_decode_segment_stream(brotli.decompress(payload))
    elif mode in (MODE_FORMAT,MODE_FORMAT_BR):o=_decode_format(mode,payload)
    else:raise ValueError("v5 mode")
    if len(o)!=n or hashlib.sha256(o).digest()!=dg:raise ValueError("v5 integrity")
    return o

def compress(data:bytes,profile:str="max")->bytes:
    data=bytes(data);candidates=v4_candidates(data,11 if profile=="max" else 6);legacy_best=min(len(a) for a,_ in candidates)
    format_candidates=[]
    if len(data)>=256 and (b"stream" in data or data.startswith(b"%PDF")):
        format_candidates=_format_candidate(data);candidates.extend(format_candidates)
    format_decisive=bool(format_candidates) and min(len(a) for a,_ in format_candidates)<legacy_best*0.80
    if len(data)>=1024 and not format_decisive:
        if len(data)>262144:sizes=[16384,32768]
        elif len(data)>65536:sizes=[4096,8192,16384,32768]
        else:sizes=[512,1024,2048,4096,8192,16384]
        for bs in sizes:
            if bs>len(data)*2:continue
            stream=_build_segment_stream(data,bs);a=_wrap5(MODE_SEG,data,stream);candidates.append((a,f"seg-{bs}"))
            probe=zlib.compress(stream,1)
            if len(probe)+8<len(stream):
                b=brotli.compress(stream,quality=11)
                if len(b)<len(stream):candidates.append((_wrap5(MODE_SEG_BR,data,b),f"seg-{bs}+br"))
    valid=[]
    for a,label in candidates:
        try:
            if decompress(a)==data:valid.append((a,label))
        except Exception:pass
    if not valid:raise RuntimeError("no exact V5 candidate")
    return min(valid,key=lambda x:(len(x[0]),x[1]))[0]

def decompress(blob:bytes)->bytes:
    if blob[:3]==MAGIC4:return v4_decompress(blob)
    if blob[:3]==MAGIC5:return _v5_decompress(blob)
    raise ValueError("unknown Fusion V5-X2 archive")

def inspect(blob:bytes)->dict:
    if blob[:3]==MAGIC4:
        n,p=vu(blob,5);return {"family":"legacy-v4","mode":blob[4],"original":n,"archive":len(blob),"ratio":n/len(blob)}
    if blob[:3]==MAGIC5:
        n,p=vu(blob,5);return {"family":"v5","mode":blob[4],"original":n,"archive":len(blob),"ratio":n/len(blob)}
    return {"family":"unknown","archive":len(blob)}
