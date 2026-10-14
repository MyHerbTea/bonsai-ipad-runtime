from pathlib import Path
import re as _build_identity_re
# Current package identity follows project.yml; historical API labels stay compatible.
_current_build_match = _build_identity_re.search(
    r'CURRENT_PROJECT_VERSION:\s*"(\d+)"',
    (Path(__file__).resolve().parents[1] / "project.yml").read_text(encoding="utf-8"),
)
assert _current_build_match is not None, "project build number is required"
_current_build = _current_build_match.group(1)
root=Path(__file__).resolve().parents[1]
engine=(root/"BonsaiLab/BonsaiEngine.swift").read_text()
view=(root/"BonsaiLab/ProductionView.swift").read_text()
server=(root/"BonsaiLab/LocalOpenAIServer.swift").read_text()
workflow=(root/".github/workflows/build-ios.yml").read_text()
project=(root/"project.yml").read_text()
patch=(root/"tools/rc126_build84_patch_prism_native_trace.py").read_text()
assert f'CURRENT_PROJECT_VERSION: "{_current_build}"' in project
assert f'RC126APIStartupLifecycle.begin(build: "{_current_build}")' in view
assert '"build_id": "rc1.26-build106-m5-governor"' in server
assert "[BUILD 84 NATIVE CONTEXT CRASH TRACE]" in view
assert "trace_present=false" in view and "trace_setup_error=" in view
assert "beginBuild84NativeContextTrace(contextLength: config.context)" in engine
assert "beginBuild84NativeContextTrace(contextLength: validated.context)" in engine
assert engine.count("defer { endBuild84NativeContextTrace() }")==2
assert "guard contextLength >= 32_768 else" in engine
assert "ctx16k-build79-validated" in view and "min(apiRuntime.gpuLayers, 56)" in view
assert "tools/rc126_build83_patch_prism_kv_sharding.py" in workflow
assert "tools/rc126_build84_patch_prism_native_trace.py" in workflow
assert "BUILD84_KV_ALLOC_BEGIN" in patch
assert "BUILD84_KV_CLEAR_BEGIN" in patch
assert "BUILD84_CTX_MEMORY_BEGIN" in patch and "BUILD84_CTX_SCHED_BEGIN" in patch
assert "::fsync(fd)" in patch and "BONSAI_BUILD84_TRACE_PATH" in patch
assert f'BonsaiLab-v1-RC1.26-build{_current_build}-b16-prefill-unsigned.ipa' in workflow
print("RC1.26 Build 84 native trace contracts: PASS")
