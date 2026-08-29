from __future__ import annotations
from dataclasses import dataclass
from difflib import SequenceMatcher

OP_COPY = 0
OP_LITERAL = 1
OP_END = 255

@dataclass(frozen=True)
class Patch:
    blob: bytes
    covered_bytes: int
    target_size: int
    @property
    def coverage_percent(self) -> float:
        return 100.0 if self.target_size == 0 else 100.0 * self.covered_bytes / self.target_size

def _put_varint(out: bytearray, n: int) -> None:
    if n < 0:
        raise ValueError("varint cannot encode negative values")
    while n >= 0x80:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)

def _get_varint(blob: bytes, pos: int) -> tuple[int, int]:
    value = 0
    shift = 0
    for _ in range(10):
        if pos >= len(blob):
            raise ValueError("truncated varint")
        b = blob[pos]
        pos += 1
        value |= (b & 0x7F) << shift
        if not (b & 0x80):
            return value, pos
        shift += 7
    raise ValueError("varint too long")

def _common_prefix(a: bytes, b: bytes) -> int:
    n = min(len(a), len(b))
    i = 0
    step = 4096
    while i + step <= n and a[i:i+step] == b[i:i+step]:
        i += step
    while i < n and a[i] == b[i]:
        i += 1
    return i

def _common_suffix(a: bytes, b: bytes, prefix: int) -> int:
    max_n = min(len(a), len(b)) - prefix
    i = 0
    step = 4096
    while i + step <= max_n and a[len(a)-i-step:len(a)-i] == b[len(b)-i-step:len(b)-i]:
        i += step
    while i < max_n and a[len(a)-1-i] == b[len(b)-1-i]:
        i += 1
    return i

def _emit_copy(out: bytearray, offset: int, n: int) -> None:
    if n <= 0:
        return
    out.append(OP_COPY)
    _put_varint(out, offset)
    _put_varint(out, n)

def _emit_literal(out: bytearray, data: bytes) -> None:
    if not data:
        return
    out.append(OP_LITERAL)
    _put_varint(out, len(data))
    out += data

def _block_middle_ops(template: bytes, data: bytes, template_offset: int, block: int = 64):
    index: dict[bytes, int] = {}
    for i in range(0, max(0, len(template)-block+1), block):
        index.setdefault(template[i:i+block], i)
    j = 0
    literal = bytearray()
    while j < len(data):
        chunk = data[j:j+block]
        if len(chunk) == block and chunk in index:
            if literal:
                yield ("lit", bytes(literal))
                literal.clear()
            yield ("copy", template_offset + index[chunk], block)
            j += block
        else:
            literal.append(data[j])
            j += 1
    if literal:
        yield ("lit", bytes(literal))

def build_patch(template: bytes, data: bytes, sequence_limit: int = 512 * 1024) -> Patch:
    out = bytearray()
    _put_varint(out, len(data))
    prefix = _common_prefix(template, data)
    suffix = _common_suffix(template, data, prefix)
    covered = 0
    if prefix:
        _emit_copy(out, 0, prefix)
        covered += prefix
    t_end = len(template) - suffix if suffix else len(template)
    d_end = len(data) - suffix if suffix else len(data)
    t_mid = template[prefix:t_end]
    d_mid = data[prefix:d_end]
    if d_mid:
        if max(len(t_mid), len(d_mid)) <= sequence_limit:
            sm = SequenceMatcher(None, t_mid, d_mid, autojunk=False)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "equal":
                    n = i2-i1
                    _emit_copy(out, prefix+i1, n)
                    covered += n
                elif tag in ("replace", "insert"):
                    _emit_literal(out, d_mid[j1:j2])
        else:
            for op in _block_middle_ops(t_mid, d_mid, prefix):
                if op[0] == "copy":
                    _, off, n = op
                    _emit_copy(out, off, n)
                    covered += n
                else:
                    _emit_literal(out, op[1])
    if suffix:
        _emit_copy(out, len(template)-suffix, suffix)
        covered += suffix
    out.append(OP_END)
    return Patch(bytes(out), covered, len(data))

def apply_patch(template: bytes, patch: bytes) -> bytes:
    target_size, pos = _get_varint(patch, 0)
    out = bytearray()
    while True:
        if pos >= len(patch):
            raise ValueError("patch missing end marker")
        op = patch[pos]
        pos += 1
        if op == OP_END:
            break
        if op == OP_COPY:
            offset, pos = _get_varint(patch, pos)
            n, pos = _get_varint(patch, pos)
            if offset+n > len(template):
                raise ValueError("patch copy outside template")
            out += template[offset:offset+n]
        elif op == OP_LITERAL:
            n, pos = _get_varint(patch, pos)
            if pos+n > len(patch):
                raise ValueError("truncated patch literal")
            out += patch[pos:pos+n]
            pos += n
        else:
            raise ValueError(f"unknown patch opcode {op}")
        if len(out) > target_size:
            raise ValueError("patch expands beyond target size")
    if pos != len(patch):
        raise ValueError("trailing bytes after patch end")
    if len(out) != target_size:
        raise ValueError("patch target size mismatch")
    return bytes(out)
