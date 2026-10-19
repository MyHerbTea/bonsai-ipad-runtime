#!/usr/bin/env python3
"""PTQ1_0 decoder parity against Prism's pinned row-dequantization ordering.

This models the C reference loop (stages 32/16/8 and qh tail), then compares
the custom register decoder's element mapping and fp16-rounded values. It is
not a substitute for compiling/executing the Metal kernel on an M5.
"""
from pathlib import Path
import random
import struct

ROOT = Path(__file__).resolve().parents[1]
PATCH = (ROOT / "tools/rc126_build113_patch_prism_ptq1_tensorops.py").read_text(encoding="utf-8")


def reference_trit(byte: int, n: int) -> int:
    # Prism stores the base-3 byte as uint8 before multiplying by three.
    q = (byte * (3 ** n)) & 0xFF
    return ((q * 3) >> 8) - 1


def lut_entry(byte: int) -> int:
    packed = 0
    for n in range(5):
        packed |= (reference_trit(byte, n) + 1) << (2 * n)
    return packed


def reference_row(qs: list[int], qh: list[int]) -> list[int]:
    # Mirrors dequantize_row_ptq1_0: stages={32,16,8}, with j carried
    # across stages. For 24 qs bytes this consumes 16 bytes then 8 bytes.
    out = []
    j = 0
    for c in (32, 16, 8):
        while j + c <= len(qs):
            for n in range(5):
                for m in range(c):
                    out.append(reference_trit(qs[j + m], n))
            j += c
    # The two qh bytes each encode four trits, interleaved by trit position.
    for n in range(4):
        for h in range(len(qh)):
            out.append(reference_trit(qh[h], n))
    assert len(out) == 128
    return out


def candidate_element(qs: list[int], qh: list[int], e: int) -> int:
    if e < 80:
        b, n = qs[e & 15], e >> 4
    elif e < 120:
        t = e - 80
        b, n = qs[16 + (t & 7)], t >> 3
    else:
        t = e - 120
        b, n = qh[t & 1], t >> 1
    return ((lut_entry(b) >> (2 * n)) & 3) - 1


def f16(value: float) -> float:
    return struct.unpack("<e", struct.pack("<e", value))[0]


assert "ptq1_0_lut[b]" in PATCH
assert "dequantize_ptq1_0_t4" not in PATCH
assert "GGML_TYPE_PTQ1_0" in PATCH
assert "block_ptq1_0" in PATCH
assert "QK_PTQ1_0" in PATCH
for needle in (
    "if (e < 80)",
    "b = block->qs[e & 15]",
    "b = block->qs[16 + (t & 7)]",
    "b = block->qh[t & 1]",
    "ptq1_0_lut[b]",
):
    assert needle in PATCH, f"custom Metal decoder mapping missing: {needle}"

for byte in range(256):
    for n in range(5):
        assert ((lut_entry(byte) >> (2 * n)) & 3) - 1 == reference_trit(byte, n)

rng = random.Random(113)
for case in range(4096):
    qs = [rng.randrange(256) for _ in range(24)]
    qh = [rng.randrange(256) for _ in range(2)]
    expected = reference_row(qs, qh)
    observed = [candidate_element(qs, qh, e) for e in range(128)]
    assert observed == expected, f"trit mapping mismatch in packed block {case}"
    for start in range(0, 128, 4):
        assert [candidate_element(qs, qh, e) for e in range(start, start + 4)] == expected[start:start + 4]
    scale = f16(rng.random() * 8.0)
    expected_half = [f16(float(v) * scale) for v in expected]
    candidate_half = [f16(float(v) * scale) for v in observed]
    assert candidate_half == expected_half, f"scaled half parity mismatch in packed block {case}"

print("PTQ1_0_CODEC_REFERENCE_PARITY: PASS (256 byte values x 5 trits; 4096 full 128-value blocks; exact reference row order; fp16 scale/output parity)")
print("GPU numerical parity: NOT_VERIFIED_PENDING_M5")
