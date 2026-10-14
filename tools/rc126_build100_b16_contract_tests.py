#!/usr/bin/env python3
"""Build100 guarded B16 static safety checks; macOS Swift XCTest-like CLI tests run in CI."""
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
policy = (root / "BonsaiLab/Build94BatchExperiment.swift").read_text()
view = (root / "BonsaiLab/ProductionView.swift").read_text()
server = (root / "BonsaiLab/LocalOpenAIServer.swift").read_text()
workflow = (root / ".github/workflows/build-ios.yml").read_text()
project = (root / "project.yml").read_text()
engine = (root / "BonsaiLab/BonsaiEngine.swift").read_text()

def has(s, needle): 
    assert needle in s, "MISSING CONTRACT: %r" % needle

has(project, f'CURRENT_PROJECT_VERSION: "{_current_build}"')
has(view, f'RC126APIStartupLifecycle.begin(build: "{_current_build}")')
has(server, '"build_id": "rc1.26-build106-m5-governor"')
has(policy, 'static let preferB16Key = "BonsaiBuild100PreferGuardedB16"')
has(policy, 'defaults.bool(forKey: confirmedKey)')
has(policy, 'defaults.bool(forKey: baselineOKKey)')
has(policy, 'defaults.set(false, forKey: preferB16Key)')
has(policy, 'defaults.set(true, forKey: pendingKey)')
has(policy, 'defaults.set("previous_candidate16_incomplete", forKey: reasonKey)')
has(policy, 'defaults.set("candidate16_startup_failed", forKey: reasonKey)')
has(policy, '"effective_next_arm": next')
has(policy, '"preferred_16_eligible": eligible')
has(view, 'apiRuntime.batch = governorDecision.profile.batch')
has(view, 'apiRuntime.ubatch = governorDecision.profile.ubatch')
has(view, 'if context == 32_768 {')
has(view, 'case .candidate16: batchCap = 16')
has(view, 'case .baseline8: batchCap = 8')
has(view, 'default: batchCap = 4')
has(view, 'isOn: $preferGuardedB16NextLaunch')
has(view, 'Build 100 · 32K 推理加速实验')
has(engine, 'contextParams.n_batch = UInt32(config.batch)')
has(engine, 'contextParams.n_ubatch = UInt32(config.ubatch)')
has(view, 'Build94BatchExperiment.noteTextSuccess(')
has(view, 'Build94BatchExperiment.noteStartupFailure()')
has(server, '/debug/build94/launch')
has(server, '/debug/build94/next-launch')
has(workflow, 'tools/rc126_build100_b16_policy_tests.swift')
has(workflow, 'tools/rc126_build100_b16_contract_tests.py')
has(workflow, f'BonsaiLab-iPad-v1-RC1.26-Build{_current_build}-B16-Prefill')
# Critical: base Build97 has no APPEND experiment, and pinned Prism is unmodified.
assert 'Build99AppendOnlyReuse' not in engine
assert 'Build98FAVecAB' not in engine
has(workflow, 'adfffbe41b2cabcd51fff326ab045662265062bb')
print("PASS Build100 process-scoped 32K B16, safe4 sticky recovery, frozen Vision/API, standalone identity")
print("NOTE: actual B16 speedup, 32K memory and Vision survival are device gates, not this source gate")
