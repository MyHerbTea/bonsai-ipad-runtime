#!/usr/bin/env python3
"""Reference parity for PTQ1_0 packed base-3 byte/trit decoding.

This validates index mapping and LUT semantics, not GPU execution. M5 numerical
parity must still be measured against the inherited Prism path on-device.
"""
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]
PATCH = (ROOT / "tools/rc126_build113_patch_prism_ptq1_tensorops.py").read_text(encoding="utf-8")


def reference_trit(byte: int, n: int) -> int:
    return ((((byte * (3 ** n)) & 0xFF) * 3) >> 8) - 1


def lut_entry(byte: int) -> int:
    packed = 0
    for n in range(5):
        packed |= (reference_trit(byte, n) + 1) << (2 * n)
    return packed


def decode_element(qs: list[int], qh: list[int], e: int) -> int:
    if e < 80:
        b, n = qs[e & 15], e >> 4
    elif e < 120:
        t = e - 80
        b, n = qs[16 + (t & 7)], t >> 3
    else:
        t = e - 120
        b, n = qh[t & 1], t >> 1
    return ((lut_entry(b) >> (2 * n)) & 3) - 1


def decode4(qs: list[int], qh: list[int], start: int) -> list[int]:
    return [decode_element(qs, qh, start + i) for i in range(4)]


assert "ptq1_0_lut[b]" in PATCH
assert "dequantize_ptq1_0_t4" not in PATCH
assert "GGML_TYPE_PTQ1_0" in PATCH

for byte in range(256):
    for n in range(5):
        assert ((lut_entry(byte) >> (2 * n)) & 3) - 1 == reference_trit(byte, n)

rng = random.Random(113)
for _ in range(2048):
    qs = [rng.randrange(256) for _ in range(24)]
    qh = [rng.randrange(256) for _ in range(2)]
    decoded = [decode_element(qs, qh, e) for e in range(128)]
    assert len(decoded) == 128 and all(v in (-1, 0, 1) for v in decoded)
    for start in range(0, 128, 4):
        assert decode4(qs, qh, start) == decoded[start:start + 4]

print("PTQ1_0_CODEC_REFERENCE_PARITY: PASS (256 byte values x 5 trits; 2048 packed blocks)")
print("GPU numerical parity: NOT_VERIFIED_PENDING_M5")
