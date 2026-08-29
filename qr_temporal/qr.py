from __future__ import annotations
from pathlib import Path
from .frames import split_frames

def write_qr_sequence(blob: bytes, unix_ns: int, out_dir: str | Path, max_frame_bytes: int = 2200) -> list[Path]:
    try: import qrcode
    except ImportError as e: raise RuntimeError("install qrcode[pil] to render QR images") from e
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    frames = split_frames(blob, unix_ns, max_frame_bytes=max_frame_bytes); paths = []
    for frame in frames:
        qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=8, border=4)
        qr.add_data(frame.bytes, optimize=0); qr.make(fit=True)
        p = out_dir / f"qtc_{unix_ns}_{frame.index+1:04d}-of-{frame.total:04d}.png"
        qr.make_image().save(p); paths.append(p)
    return paths
