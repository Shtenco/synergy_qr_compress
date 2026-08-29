from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
import bz2, hashlib, lzma, struct, time, zlib
from typing import Iterable

from .qtd2 import fastcdc as _qtd2_fastcdc
from .rans import compress as rans_compress, decompress as rans_decompress

MODEL_MAGIC = b"QD3M"
CONTAINER_MAGIC = b"Q4B1"
MODEL_HEADER = struct.Struct(">4sBI")
ENTRY_HEADER = struct.Struct(">QH32sBII")
CONTAINER_HEADER = struct.Struct(">4sBBBBQIIII16s32s")  # 80 B
MODEL_RAW, MODEL_BROTLI, MODEL_ZLIB = range(3)
RAW, ZLIB, BZ2, LZMA, BROTLI, RANS, ZSTD, GABRIEL = range(8)
EXTERNAL_LZ, FASTCDC, LINES, LINEAGE, STANDALONE = range(5)
CODEC_NAMES = ("raw","zlib-9","bz2-9","lzma-extreme","brotli-11","rans-o0",
               "zstd-19-temporal-dict","gabriel-horn-max")
STRATEGY_NAMES = ("temporal-external-lz","fastcdc-global-ref","exact-line-ref",
                  "path-lineage","standalone")
OP_COPY, OP_LITERAL = 0, 1


def _uv(n: int) -> bytes:
    if n < 0: raise ValueError("negative uvarint")
    out = bytearray()
    while n >= 128:
        out.append((n & 127) | 128); n >>= 7
    out.append(n)
    return bytes(out)


def _ruv(data: bytes, pos: int) -> tuple[int,int]:
    n = shift = 0
    for _ in range(10):
        if pos >= len(data): raise ValueError("truncated uvarint")
        b = data[pos]; pos += 1
        n |= (b & 127) << shift
        if b < 128: return n, pos
        shift += 7
    raise ValueError("uvarint too large")


@dataclass(frozen=True)
class RepoBlob:
    path: str
    unix_ns: int
    data: bytes


@dataclass(frozen=True)
class QTD3Entry:
    path: str
    unix_ns: int
    digest: bytes
    data: bytes


@dataclass(frozen=True)
class QTD3Model:
    entries: tuple[QTD3Entry,...]
    model_id: bytes

    @property
    def max_unix_ns(self) -> int:
        return max((e.unix_ns for e in self.entries), default=0)

    @property
    def leakage_guard(self) -> set[bytes]:
        return {e.digest for e in self.entries}

    def to_bytes(self) -> bytes:
        out = bytearray(MODEL_HEADER.pack(MODEL_MAGIC, 1, len(self.entries)))
        for e in self.entries:
            path = e.path.encode()
            if len(path) > 65535: raise ValueError("path too long")
            candidates = [(MODEL_RAW,e.data),(MODEL_ZLIB,zlib.compress(e.data,9))]
            try:
                import brotli
                candidates.append((MODEL_BROTLI,brotli.compress(e.data,quality=11)))
            except Exception: pass
            codec,payload = min(candidates,key=lambda x:(len(x[1]),x[0]))
            out += ENTRY_HEADER.pack(e.unix_ns,len(path),e.digest,codec,len(e.data),len(payload))
            out += path + payload
        return bytes(out)

    @classmethod
    def from_bytes(cls, blob: bytes) -> "QTD3Model":
        if len(blob) < MODEL_HEADER.size: raise ValueError("truncated QTD3 model")
        magic,version,count = MODEL_HEADER.unpack_from(blob)
        if magic != MODEL_MAGIC or version != 1: raise ValueError("unsupported QTD3 model")
        pos=MODEL_HEADER.size; entries=[]
        for _ in range(count):
            if pos+ENTRY_HEADER.size > len(blob): raise ValueError("truncated QTD3 entry")
            ts,plen,digest,codec,n,pn = ENTRY_HEADER.unpack_from(blob,pos); pos += ENTRY_HEADER.size
            if pos+plen+pn > len(blob): raise ValueError("truncated QTD3 entry payload")
            path=blob[pos:pos+plen].decode(); pos += plen
            payload=blob[pos:pos+pn]; pos += pn
            if codec == MODEL_RAW: data=payload
            elif codec == MODEL_ZLIB: data=zlib.decompress(payload)
            elif codec == MODEL_BROTLI:
                import brotli; data=brotli.decompress(payload)
            else: raise ValueError("unknown QTD3 model codec")
            if len(data)!=n or hashlib.sha256(data).digest()!=digest:
                raise ValueError("QTD3 model integrity mismatch")
            entries.append(QTD3Entry(path,ts,digest,data))
        if pos != len(blob): raise ValueError("trailing QTD3 model bytes")
        model=cls(tuple(entries),b"")
        return cls(model.entries,hashlib.sha256(blob).digest())


def train_qtd3(blobs: Iterable[RepoBlob]) -> QTD3Model:
    rows=[]; seen=set()
    for b in blobs:
        data=bytes(b.data); digest=hashlib.sha256(data).digest()
        key=(str(b.path),int(b.unix_ns),digest)
        if key in seen: continue
        seen.add(key); rows.append(QTD3Entry(str(b.path),int(b.unix_ns),digest,data))
    if not rows: raise ValueError("at least one repository blob is required")
    rows.sort(key=lambda e:(e.unix_ns,e.path,e.digest))
    model=QTD3Model(tuple(rows),b""); blob=model.to_bytes()
    return QTD3Model(model.entries,hashlib.sha256(blob).digest())


def _copy(out: bytearray, ei: int, off: int, n: int):
    out.append(OP_COPY); out += _uv(ei)+_uv(off)+_uv(n)


def _lit(out: bytearray, data: bytes):
    if data: out.append(OP_LITERAL); out += _uv(len(data))+data


def _decode_tokens(tokens: bytes, model: QTD3Model, expected: int) -> bytes:
    out=bytearray(); pos=0
    while pos < len(tokens):
        op=tokens[pos]; pos+=1
        if op == OP_COPY:
            ei,pos=_ruv(tokens,pos); off,pos=_ruv(tokens,pos); n,pos=_ruv(tokens,pos)
            if ei >= len(model.entries): raise ValueError("copy entry out of range")
            src=model.entries[ei].data
            if off+n > len(src): raise ValueError("copy range out of range")
            out += src[off:off+n]
        elif op == OP_LITERAL:
            n,pos=_ruv(tokens,pos)
            if pos+n > len(tokens): raise ValueError("truncated literal")
            out += tokens[pos:pos+n]; pos += n
        else: raise ValueError("unknown token")
        if len(out) > expected: raise ValueError("output exceeds target")
    if len(out) != expected: raise ValueError("target size mismatch")
    return bytes(out)


def _seed_index(model: QTD3Model, seed: int, cap: int=128):
    idx=defaultdict(list)
    for ei,e in enumerate(model.entries):
        for p in range(max(0,len(e.data)-seed+1)):
            bucket=idx[e.data[p:p+seed]]
            if len(bucket)<cap: bucket.append((ei,p))
    return idx


def _external(target: bytes, path: str, model: QTD3Model, seed: int, mm: int, idx):
    same={i for i,e in enumerate(model.entries) if e.path==path}
    out=bytearray(); pending=bytearray(); covered=refs=0
    def flush():
        if pending: _lit(out,bytes(pending)); pending.clear()
    i=0
    while i < len(target):
        best=(0,0,0)
        if i+seed <= len(target):
            cand=idx.get(target[i:i+seed],())
            cand=sorted(cand,key=lambda x:(0 if x[0] in same else 1,-model.entries[x[0]].unix_ns))
            for ei,off in cand:
                src=model.entries[ei].data; n=seed; limit=min(len(target)-i,len(src)-off)
                while n<limit and target[i+n]==src[off+n]: n+=1
                if n>best[0]: best=(n,ei,off)
        if best[0]>=mm:
            flush(); _copy(out,best[1],best[2],best[0]); covered+=best[0]; refs+=1; i+=best[0]
        else: pending.append(target[i]); i+=1
    flush()
    return bytes(out),covered,refs,len(target)-covered


def _fastcdc_tokens(target: bytes, model: QTD3Model, profile):
    index={}
    for ei,e in enumerate(model.entries):
        off=0
        for chunk in _qtd2_fastcdc(e.data,*profile):
            d=hashlib.blake2b(chunk,digest_size=16).digest()
            index.setdefault(d,(ei,off,len(chunk))); off+=len(chunk)
    out=bytearray(); pending=bytearray(); covered=refs=0
    def flush():
        if pending: _lit(out,bytes(pending)); pending.clear()
    for chunk in _qtd2_fastcdc(target,*profile):
        ref=index.get(hashlib.blake2b(chunk,digest_size=16).digest())
        if ref is None: pending += chunk
        else: flush(); _copy(out,*ref); covered+=len(chunk); refs+=1
    flush()
    return bytes(out),covered,refs,len(target)-covered


def _lines(target: bytes, model: QTD3Model):
    index={}
    for ei,e in enumerate(model.entries):
        off=0
        for line in e.data.splitlines(keepends=True):
            if len(line)>=4: index.setdefault(line,(ei,off,len(line)))
            off+=len(line)
    out=bytearray(); pending=bytearray(); covered=refs=0
    def flush():
        if pending: _lit(out,bytes(pending)); pending.clear()
    for line in target.splitlines(keepends=True):
        ref=index.get(line)
        if ref is None: pending += line
        else: flush(); _copy(out,*ref); covered+=len(line); refs+=1
    flush()
    return bytes(out),covered,refs,len(target)-covered


def _lineage(target: bytes, path: str, model: QTD3Model):
    cand=[(i,e) for i,e in enumerate(model.entries) if e.path==path]
    if not cand: return None
    ei,base=max(cand,key=lambda x:x[1].unix_ns)
    out=bytearray(); pos=0; covered=refs=0
    for b in SequenceMatcher(None,base.data,target,autojunk=False).get_matching_blocks():
        if not b.size: continue
        _lit(out,target[pos:b.b]); _copy(out,ei,b.a,b.size)
        covered+=b.size; refs+=1; pos=b.b+b.size
    _lit(out,target[pos:])
    return bytes(out),covered,refs,len(target)-covered


def _zstd_dict(model: QTD3Model):
    try: import zstandard as zstd
    except Exception: return None,None
    samples=[e.data for e in model.entries if 16<=len(e.data)<=131072]
    if len(samples)<4 or sum(map(len,samples))<1024: return zstd,None
    try: return zstd,zstd.train_dictionary(min(16384,max(512,sum(map(len,samples))//4)),samples)
    except Exception: return zstd,None


def _gabriel():
    for module in ("compression_lab.gabriel_horn_engine","gabriel_horn_engine"):
        try:
            m=__import__(module,fromlist=["GabrielHornEngine"])
            return m.GabrielHornEngine(profile="max",surface_weight=0.0,work_weight=0.0)
        except Exception: pass
    return None


def _compress(tokens: bytes, model: QTD3Model):
    c=[(RAW,tokens),(ZLIB,zlib.compress(tokens,9)),(BZ2,bz2.compress(tokens,9)),
       (LZMA,lzma.compress(tokens,preset=9|lzma.PRESET_EXTREME))]
    try:
        import brotli; c.append((BROTLI,brotli.compress(tokens,quality=11)))
    except Exception: pass
    try: c.append((RANS,rans_compress(tokens)))
    except Exception: pass
    zstd,trained=_zstd_dict(model)
    if zstd:
        try:
            kw=dict(level=19,write_checksum=True,write_content_size=True)
            if trained is not None: kw["dict_data"]=trained
            c.append((ZSTD,zstd.ZstdCompressor(**kw).compress(tokens)))
        except Exception: pass
    g=_gabriel()
    if g:
        try:
            a=g.compress(tokens)
            if g.decompress(a)==tokens: c.append((GABRIEL,a))
        except Exception: pass
    return c


def _decompress(codec: int, payload: bytes, model: QTD3Model, n: int):
    if codec==RAW: data=payload
    elif codec==ZLIB: data=zlib.decompress(payload)
    elif codec==BZ2: data=bz2.decompress(payload)
    elif codec==LZMA: data=lzma.decompress(payload)
    elif codec==BROTLI:
        import brotli; data=brotli.decompress(payload)
    elif codec==RANS: data=rans_decompress(payload)
    elif codec==ZSTD:
        import zstandard as zstd
        _,trained=_zstd_dict(model)
        d=zstd.ZstdDecompressor(dict_data=trained) if trained is not None else zstd.ZstdDecompressor()
        data=d.decompress(payload,max_output_size=n)
    elif codec==GABRIEL:
        g=_gabriel()
        if not g: raise ValueError("Gabriel unavailable")
        data=g.decompress(payload)
    else: raise ValueError("unknown codec")
    if len(data)!=n: raise ValueError("token size mismatch")
    return data


@dataclass(frozen=True)
class PackedQTD3:
    blob: bytes
    codec_id: int
    strategy_id: int
    unix_ns: int
    original_size: int
    token_size: int
    payload_size: int
    covered_bytes: int
    ref_count: int
    literal_bytes: int

    @property
    def coverage_percent(self): return 100.0 if not self.original_size else 100*self.covered_bytes/self.original_size


def pack_blind_v3(target: bytes, path: str, model: QTD3Model, *, unix_ns: int|None=None):
    target=bytes(target); digest=hashlib.sha256(target).digest()
    if digest in model.leakage_guard: raise ValueError("QTD3 blind violation: target SHA-256 exists in training model")
    ts=time.time_ns() if unix_ns is None else int(unix_ns)
    if model.max_unix_ns >= ts: raise ValueError("QTD3 temporal leakage: model contains data at or after target time")
    routes=[]
    for seed in (4,5,6,8,10):
        idx=_seed_index(model,seed)
        for mm in (8,10,12,16,24,32):
            if mm>=seed: routes.append((EXTERNAL_LZ,*_external(target,path,model,seed,mm,idx)))
    for profile in ((8,16,32),(16,32,64),(24,48,96),(48,96,192)):
        routes.append((FASTCDC,*_fastcdc_tokens(target,model,profile)))
    routes.append((LINES,*_lines(target,model)))
    lin=_lineage(target,path,model)
    if lin: routes.append((LINEAGE,*lin))
    direct=bytearray(); _lit(direct,target); routes.append((STANDALONE,bytes(direct),0,0,len(target)))
    valid=[]
    for strategy,tokens,covered,refs,literal in routes:
        for codec,payload in _compress(tokens,model):
            try:
                if _decompress(codec,payload,model,len(tokens)) != tokens: continue
                if _decode_tokens(tokens,model,len(target)) != target: continue
                valid.append((len(payload),len(tokens),-covered,strategy,codec,tokens,payload,covered,refs,literal))
            except Exception: pass
    if not valid: raise RuntimeError("no valid QTD3 route")
    _,_,_,strategy,codec,tokens,payload,covered,refs,literal=min(valid)
    header=CONTAINER_HEADER.pack(CONTAINER_MAGIC,1,codec,strategy,0,ts,len(target),len(tokens),
                                 len(payload),covered,model.model_id[:16],digest)
    return PackedQTD3(header+payload,codec,strategy,ts,len(target),len(tokens),len(payload),covered,refs,literal)


def unpack_v3(blob: bytes, model: QTD3Model):
    if len(blob)<CONTAINER_HEADER.size: raise ValueError("truncated QTD3 container")
    magic,version,codec,strategy,flags,ts,n,tn,pn,covered,mid,digest=CONTAINER_HEADER.unpack_from(blob)
    if magic!=CONTAINER_MAGIC or version!=1: raise ValueError("unsupported QTD3 container")
    if model.model_id[:16]!=mid: raise ValueError("QTD3 model fingerprint mismatch")
    if model.max_unix_ns>=ts: raise ValueError("QTD3 model violates temporal cutoff")
    if len(blob)!=CONTAINER_HEADER.size+pn: raise ValueError("QTD3 payload length mismatch")
    tokens=_decompress(codec,blob[CONTAINER_HEADER.size:],model,tn)
    target=_decode_tokens(tokens,model,n)
    if hashlib.sha256(target).digest()!=digest: raise ValueError("QTD3 target SHA-256 mismatch")
    return target


def inspect_v3(blob: bytes, model: QTD3Model|None=None):
    magic,version,codec,strategy,flags,ts,n,tn,pn,covered,mid,digest=CONTAINER_HEADER.unpack_from(blob)
    if magic!=CONTAINER_MAGIC or version!=1: raise ValueError("unsupported QTD3 container")
    out={"version":version,"codec_id":codec,"codec":CODEC_NAMES[codec],"strategy_id":strategy,
         "strategy":STRATEGY_NAMES[strategy],"unix_ns":ts,"original_size":n,"token_size":tn,
         "payload_size":pn,"container_size":len(blob),"covered_bytes":covered,"literal_bytes":n-covered,
         "model_coverage_percent":100.0 if not n else 100*covered/n,
         "transport_reduction_percent":100.0 if not n else 100*(1-len(blob)/n),
         "model_id16":mid.hex(),"sha256":digest.hex(),"header_size":CONTAINER_HEADER.size}
    if model:
        out["model_match"]=model.model_id[:16]==mid
        out["temporal_cutoff_valid"]=model.max_unix_ns<ts
        out["model_serialized_bytes"]=len(model.to_bytes())
    return out
