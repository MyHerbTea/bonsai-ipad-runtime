#!/usr/bin/env python3
"""Source contracts for the opt-in PTQ1_0 TensorOps candidate."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "tools/rc126_build113_patch_prism_ptq1_tensorops.py"
ENGINE = ROOT / "BonsaiLab/BonsaiEngine.swift"
POLICY = ROOT / "BonsaiLab/Build113MetalTensorPolicy.swift"
PRODUCTION = ROOT / "BonsaiLab/ProductionView.swift"
SERVER = ROOT / "BonsaiLab/LocalOpenAIServer.swift"
WORKFLOW = ROOT / ".github/workflows/build112-b16-default.yml"
DOC = ROOT / "docs/optimization/backburner-integration/RC1.26_BUILD113_PTQ1_TENSOROPS_01.md"

patch = PATCH.read_text(encoding="utf-8")
engine = ENGINE.read_text(encoding="utf-8")
policy = POLICY.read_text(encoding="utf-8")
production = PRODUCTION.read_text(encoding="utf-8")
server = SERVER.read_text(encoding="utf-8")
workflow = WORKFLOW.read_text(encoding="utf-8")
doc = DOC.read_text(encoding="utf-8")

for needle in (
    "adfffbe41b2cabcd51fff326ab045662265062bb",
    "GGML_TYPE_PTQ1_0",
    "op->src[1]->type == GGML_TYPE_F32",
    "props_dev->device_id >= GGML_METAL_DEVICE_M5",
    "ne00 % QK_PTQ1_0 == 0",
    "ne11 >= BONSAI_M5_PTQ1_TENSOROPS_BM",
    "ne11 % BONSAI_M5_PTQ1_TENSOROPS_BM == 0",
    "ne01 >= BONSAI_M5_PTQ1_TENSOROPS_BN",
    "ptq1_0_lut[b]",
    "kernel_mul_mm_ptq1_tensorops_0_f32",
    "ptq1_tensorops_pipeline_failed.store(true",
    "BUILD113_PTQ1_TENSOROPS_INPUT_TYPE_OBSERVED",
    "BUILD113_PTQ1_TENSOROPS_ROUTE_SELECTED",
    "BUILD113_PTQ1_TENSOROPS_PIPELINE_READY",
    "BUILD113_PTQ1_TENSOROPS_DISPATCH_ENQUEUED",
    "BUILD113_PTQ1_TENSOROPS_FALLBACK_TO_PRISM",
):
    assert needle in patch, f"PTQ1 candidate contract missing: {needle}"
assert "dequantize_ptq1_0_t4" not in patch
assert "block_pq2_0" in patch and "block_ptq1_0" in patch
assert "allowMetalTensorCandidate" in policy
assert "BonsaiBuild113PTQ1TensorOpsAB16Enabled" in engine
assert "config.context == 16_384" in engine
assert "config.batch == 16" in engine and "config.ubatch == 16" in engine
assert "enableBuild113PTQ1TensorTrace" in engine
assert "实验：PTQ1_0 A/B 固定 16K / B16（下次启动）" in production
assert "BonsaiBuild113PTQ1TensorOpsAB16Enabled" in production
assert "apiRuntime.batch = 16" in production and "apiRuntime.ubatch = 16" in production
assert "ptq1_tensorops_trace" in server
assert "metal_current_allocated_bytes" in server
assert "metal_working_set_headroom_bytes" in server and "thermal_state" in server
assert "ptq1_0_lut" in doc
assert "rc126_build113_patch_prism_ptq1_tensorops.py" in workflow
assert "rc126_build113_ptq1_tensorops_codec_tests.py" in workflow
assert "verify_ptq1_tensorops_binary.sh" in workflow
assert "kernel_mul_mm_ptq1_tensorops_0_f32" in workflow
print("BUILD113_PTQ1_TENSOROPS_CONTRACT: PASS")
