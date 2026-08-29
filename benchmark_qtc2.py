from __future__ import annotations
import argparse
import json
import os
from qr_temporal import TemporalSample, train_temporal_dictionary, pack, pack_v2, unpack_v2, inspect_v2

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bytes", type=int, default=1_000_000)
    args = ap.parse_args()
    n = max(1, args.bytes)
    base = os.urandom(n)
    ts = 1787990000000000000
    model = train_temporal_dictionary([TemporalSample(ts, base)])

    exact = pack_v2(base, model=model)
    exact_restored = unpack_v2(exact.blob, model)

    changed = bytearray(base)
    changed[n // 2] ^= 0x5A
    changed = bytes(changed)
    patch = pack_v2(changed, model=model)
    patch_restored = unpack_v2(patch.blob, model)
    qtc1 = pack(changed, unix_ns=ts)

    result = {
        "input_bytes": n,
        "model_bytes": len(model.to_bytes()),
        "exact": inspect_v2(exact.blob, model),
        "one_byte_mutation": inspect_v2(patch.blob, model),
        "qtc1_mutated_container_bytes": len(qtc1.blob),
        "qtc2_mutated_container_bytes": len(patch.blob),
        "qtc2_vs_qtc1_savings_percent": 100.0 * (1.0 - len(patch.blob) / len(qtc1.blob)),
        "exact_roundtrip": exact_restored == base,
        "patch_roundtrip": patch_restored == changed,
    }
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
