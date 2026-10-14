#!/usr/bin/env python3
"""Build102 source/packaging safety contracts. Device perf is a separate gate."""
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
engine = (root / "BonsaiLab/BonsaiEngine.swift").read_text()
project = (root / "project.yml").read_text()

def required(text, item):
    assert item in text, f"Missing safety invariant: {item}"

for arm in ('candidate16 = "CANDIDATE16"', 'candidate24 = "CANDIDATE24"',
            'candidate32 = "CANDIDATE32"'):
    required(policy, arm)
for item in (
    'candidate24CompletedKey', 'candidate32CompletedKey',
    'acknowledgeHigherRisk: Bool = false',
    'if arm == .candidate24 &&',
    'if arm == .candidate32 &&',
    'if arm == .candidate16 || arm == .candidate24 || arm == .candidate32',
    'defaults.set(true, forKey: pendingKey)',
    'previous_candidate16_incomplete',
    'defaults.set(true, forKey: fallbackKey)',
    'defaults.set(Arm.safe4.rawValue, forKey: nextKey)',
    'guard promptTokens >= 200 else { return }',
    'defaults.set(false, forKey: preferB16Key)',
):
    required(policy, item)
for item in (
    'case .candidate16: batchCap = 16',
    'case .candidate24: batchCap = 24',
    'case .candidate32: batchCap = 32',
    'case .baseline8: batchCap = 8',
    'default: batchCap = 4',
    'apiRuntime.batch = governorDecision.profile.batch',
    'apiRuntime.ubatch = governorDecision.profile.ubatch',
    'if context == 32_768 {',
    f'RC126APIStartupLifecycle.begin(build: "{_current_build}")',
    'Build94BatchExperiment.noteTextSuccess(',
    'Build94BatchExperiment.noteStartupFailure()',
):
    required(view, item)
for item in (
    '"build_id": "rc1.26-build106-m5-governor"',
    '"/debug/build102/next-launch"',
    '"/debug/build102/launch"',
    'acknowledge_higher_risk',
    'acknowledgeHigherRisk: higherRiskConsent',
    '"candidate32_requires_explicit_consent"',
    '"active_batch"',
    '"engine_context_batch"',
):
    required(server, item)
for item in (
    f'CURRENT_PROJECT_VERSION: "{_current_build}"',
    ):
    required(project, item)
for item in (
    'tools/rc126_build102_batch_policy_tests.swift',
    'tools/rc126_build102_batch_contract_tests.py',
    f'BonsaiLab-iPad-v1-RC1.26-Build{_current_build}-B16-Prefill',
    'adfffbe41b2cabcd51fff326ab045662265062bb',
):
    required(workflow, item)
required(engine, 'contextParams.n_batch = UInt32(config.batch)')
required(engine, 'contextParams.n_ubatch = UInt32(config.ubatch)')
assert 'Build99AppendOnlyReuse' not in engine, "failed append experiment leaked"
assert 'Build98FAVecAB' not in engine, "NE tuning leaked"
print('PASS: Build102 guarded one-shot 24/32, exact 32K shapes, B16 qualification, sticky recovery')
print('DEVICE REQUIRED: no speed, memory headroom, output quality or vision claim from source test')
