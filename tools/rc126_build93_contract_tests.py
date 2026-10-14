#!/usr/bin/env python3
"""Structural integration invariants; real Swift lifecycle behavior is tested separately."""
from pathlib import Path
import re as _build_identity_re
# Current package identity follows project.yml; historical API labels stay compatible.
_current_build_match = _build_identity_re.search(
    r'CURRENT_PROJECT_VERSION:\s*"(\d+)"',
    (Path(__file__).resolve().parents[1] / "project.yml").read_text(encoding="utf-8"),
)
assert _current_build_match is not None, "project build number is required"
_current_build = _current_build_match.group(1)
root = Path(__file__).resolve().parents[1]
view = (root / "BonsaiLab/ProductionView.swift").read_text()
engine = (root / "BonsaiLab/BonsaiEngine.swift").read_text()
server = (root / "BonsaiLab/LocalOpenAIServer.swift").read_text()
policy = (root / "BonsaiLab/Build93BatchTrialPolicy.swift").read_text()
project = (root / "project.yml").read_text()
assert f'CURRENT_PROJECT_VERSION: "{_current_build}"' in project
assert f'RC126APIStartupLifecycle.begin(build: "{_current_build}")' in view
assert '"build_id": "rc1.26-build106-m5-governor"' in server
assert '"schema": "bonsai-build94-execution-v1"' in server
assert 'Build94BatchExperiment.select(context: context)' in view
assert 'case .candidate16: batchCap = 16' in view
assert 'apiRuntime.batch = min(apiRuntime.batch, batchCap)' in view
assert 'apiRuntime.ubatch = min(apiRuntime.ubatch, batchCap)' in view
assert 'Build94BatchExperiment.noteTextSuccess(' in view
assert 'Build94BatchExperiment.noteStartupFailure()' in view
assert view.index('Phase2FPrefillBatchLaunchLatch.apply(') < view.index('applyBuild82LongContextPolicy(', view.index('private func startAPIServer()'))
assert 'contextParams.n_batch = UInt32(config.batch)' in engine
assert 'contextParams.n_ubatch = UInt32(config.ubatch)' in engine
assert ('batchSize:\n                        appliedRuntime.batch' in engine or
        'batchSize: appliedRuntime.batch' in engine), "32K prefill must use effective runtime batch"
assert 'onProgress?("decode_begin"' in engine
assert 'onProgress?("decode_end"' in engine
for field in ['"batch_trial"', '"engine_context_batch"', '"engine_context_ubatch"', '"pending"', '"sticky_fallback"']:
    assert field in server
for field in ['pendingKey', 'fallbackKey', 'confirmedKey', 'reasonKey', 'modeKey']:
    assert field in policy
print("Build93 integration source contract: PASS (behavior checked by Swift executable test)")
