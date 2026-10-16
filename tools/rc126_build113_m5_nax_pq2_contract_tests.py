#!/usr/bin/env python3
"""Contract checks for the M5-NAX-PQ2-01 candidate."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "tools/rc126_build113_patch_prism_m5_nax_pq2.py"
WORKFLOW = ROOT / ".github/workflows/m5-nax-pq2-01.yml"
DOC = ROOT / "docs/optimization/backburner-integration/RC1.26_BUILD113_M5_NAX_PQ2_01.md"

def require(path: Path, *needles: str) -> None:
    source = path.read_text(encoding="utf-8")
    for needle in needles:
        assert needle in source, f"{needle!r} missing from {path}"

require(
    PATCH,
    "adfffbe41b2cabcd51fff326ab045662265062bb",
    "BONSAI_M5_NAX_PQ2_01",
    "GGML_TYPE_PQ2_0",
    "GGML_METAL_PQ2_NAX_DISABLE",
    "get_left_input_cooperative_tensor",
    "kernel_mul_mm_nax_pq2_0_f32",
    "BONSAI_M5_NAX_PQ2_BM 64",
    "BONSAI_M5_NAX_PQ2_BN 128",
    "BONSAI_M5_NAX_PQ2_NSG 8",
)

require(
    WORKFLOW,
    "lab/m5-nax-pq2-01",
    "adfffbe41b2cabcd51fff326ab045662265062bb",
    "rc126_build113_patch_prism_m5_nax_pq2.py",
    "build-xcframework.sh ios-device",
    "M5-NAX-PQ2-01",
)

require(
    DOC,
    "Build112",
    "adfffbe41b2cabcd51fff326ab045662265062bb",
    "PQ2_0",
    "cooperative tensor",
    "NOT DEVICE CERTIFIED",
)

print("BUILD113_M5_NAX_PQ2_CONTRACT: PASS")
