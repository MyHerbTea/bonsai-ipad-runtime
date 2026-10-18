#!/usr/bin/env python3
"""Static regression checks for crash-persistent Build112 native startup tracing."""
from pathlib import Path

engine = Path("BonsaiLab/BonsaiEngine.swift").read_text(encoding="utf-8")
view = Path("BonsaiLab/ProductionView.swift").read_text(encoding="utf-8")
workflow = Path(".github/workflows/build112-b16-default.yml").read_text(encoding="utf-8")

assert "func beginAPIStartupNativeTrace(" in engine
assert "func recordAPIStartupNativeTrace(_ event: String)" in engine
assert "func endAPIStartupNativeTrace(_ event: String)" in engine
assert "Darwin.fsync(fd)" in engine
assert "SWIFT_MODEL_MMAP_BEGIN" in engine
assert "SWIFT_MODEL_MMAP_DONE" in engine
assert "SWIFT_ENGINE_COLD_START_BACKEND_INIT_BEGIN" in engine
assert "SWIFT_ENGINE_COLD_START_BACKEND_INIT_DONE" in engine

start = view.index("private func startAPIServer()")
begin = view.index("await sharedEngine.beginAPIStartupNativeTrace(", start)
vision_release = view.index("releaseResidentStateForContextSwitch()", start)
prewarm = view.index("try await sharedEngine.prepareAPIColdStart(", start)
model_load = view.index("try await sharedEngine.loadModel(", start)
caught_error = view.index('await sharedEngine.endAPIStartupNativeTrace(\n                    "SWIFT_API_START_CAUGHT_ERROR"', start)
assert begin < vision_release < prewarm < model_load < caught_error

trace_method = engine.index("private func beginBuild84NativeContextTrace(")
trace_method_end = engine.index("private func appendBuild84NativeContextTraceLine(", trace_method)
trace_body = engine[trace_method:trace_method_end]
reuse_guard = trace_body.index("if build84NativeContextTraceActive")
header_write = trace_body.index("try header.write(to: url")
assert reuse_guard < header_write, "re-entering trace setup must reuse the current attempt, not rotate it"
assert "let nativeTraceEnabled = M5RuntimeGovernor.shouldEnableNativeContextTrace(" in trace_body
assert "guard M5RuntimeGovernor.shouldEnableNativeContextTrace(" not in trace_body, "safe B8 starts must also create a Swift trace"
assert "build84NativeContextTraceNativeEnabled" in trace_body
assert "SWIFT_TRACE_FILE_READY" in trace_body

trace_export = view[view.index('Button("复制完整原生崩溃追踪（当前及上次）")'):]
assert "trace_setup_error=\\(traceSetupError)" in trace_export
assert "app_source_sha=\\(BonsaiCertificationBuildIdentity.sourceGitSHA)" in trace_export
assert "current_trace_exists=\\(FileManager.default.fileExists(atPath: currentURL.path))" in trace_export
assert "configured_api_context=\\(selectedAPIContextValue)" in trace_export

end_method = engine.index("private func endBuild84NativeContextTrace()")
end_method_body = engine[end_method:engine.index("// Keep the NAX-only trace", end_method)]
assert "build84NativeContextTraceURL = nil" not in end_method_body, "retain URL so caught errors can be appended"

assert "python3 tools/build112_native_trace_startup_contract_tests.py" in workflow
print("PASS Build112 always-on Swift startup trace, gated native trace, durable append, export metadata, and same-attempt reuse")
