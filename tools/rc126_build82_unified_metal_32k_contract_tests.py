from pathlib import Path
import re as _build_identity_re
# Current package identity follows project.yml; historical API labels stay compatible.
_current_build_match = _build_identity_re.search(
    r'CURRENT_PROJECT_VERSION:\s*"(\d+)"',
    (Path(__file__).resolve().parents[1] / "project.yml").read_text(encoding="utf-8"),
)
assert _current_build_match is not None, "project build number is required"
_current_build = _current_build_match.group(1)

ROOT = Path(__file__).resolve().parents[1]
view = (ROOT / "BonsaiLab/ProductionView.swift").read_text(encoding="utf-8")
engine = (ROOT / "BonsaiLab/BonsaiEngine.swift").read_text(encoding="utf-8")
server = (ROOT / "BonsaiLab/LocalOpenAIServer.swift").read_text(encoding="utf-8")
project = (ROOT / "project.yml").read_text(encoding="utf-8")
workflow = (ROOT / ".github/workflows/build-ios.yml").read_text(encoding="utf-8")

assert ('CURRENT_PROJECT_VERSION: "82"' in project or f'CURRENT_PROJECT_VERSION: "{_current_build}"' in project)
assert ('RC126APIStartupLifecycle.begin(build: "82")' in view or f'RC126APIStartupLifecycle.begin(build: "{_current_build}")' in view)
assert ("RC1.26 Build 82 Unified-Metal 32K Lab" in view or "RC1.26 Build 89 Compact Scheduler Metadata" in view)
assert ('"build_id": "rc1.26-build82-unified-metal-32k-lab"' in server or '"build_id": "rc1.26-build106-m5-governor"' in server)
assert "private func applyBuild82LongContextPolicy(" in view
assert view.count("applyBuild82LongContextPolicy(") == 3
assert "ctx16k-build79-validated" in view
assert "min(apiRuntime.gpuLayers, 56)" in view
assert "ctx32k-q4-unified-metal-gpu99-b4" in view
assert "apiRuntime.gpuLayers = 99" in view
assert "apiRuntime.batch = min(apiRuntime.batch, batchCap)" in view and "case .candidate16: batchCap = 16" in view
assert "apiRuntime.ubatch = min(apiRuntime.ubatch, batchCap)" in view and "case .candidate16: batchCap = 16" in view
assert "apiRuntime.offloadKQV = true" in view
assert "apiRuntime.opOffload = true" in view
assert (
    "[BUILD 82 EFFECTIVE LONG CONTEXT]" in view
    or "[BUILD 83 EFFECTIVE LONG CONTEXT]" in view
)
for marker in [
    "BonsaiBuild82EngineModelGPULayers",
    "BonsaiBuild82ModelLoadCompleted",
    "BonsaiBuild82EngineContextBatch",
    "BonsaiBuild82EngineContextUBatch",
]:
    assert marker in engine, marker
for field in [
    "build82_unified_metal_profile",
    "build82_effective_batch",
    "build82_effective_ubatch",
    "build82_effective_gpu_layers",
    "build82_flash_attention",
    "build82_offload_kqv",
    "build82_op_offload",
    "build82_engine_model_gpu_layers",
    "build82_model_load_completed",
    "build82_engine_context_batch",
    "build82_engine_context_ubatch",
]:
    assert field in server, field
assert "RC1.26 Build 82 unified-Metal 32K contracts" in workflow
assert "tools/rc126_build82_unified_metal_32k_contract_tests.py" in workflow
assert (
    "BonsaiLab-v1-RC1.26-build82-unified-metal-32k-lab-unsigned.ipa" in workflow
    or f'BonsaiLab-v1-RC1.26-build{_current_build}-b16-prefill-unsigned.ipa' in workflow
)
assert (
    "BonsaiLab-iPad-v1-RC1.26-Build82-Unified-Metal-32K-Lab" in workflow
    or f'BonsaiLab-iPad-v1-RC1.26-Build{_current_build}-B16-Prefill' in workflow
)
print("RC1.26 Build 82 unified-Metal 32K contracts: PASS")
