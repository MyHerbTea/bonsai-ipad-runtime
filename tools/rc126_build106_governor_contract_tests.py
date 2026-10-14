#!/usr/bin/env python3
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
read = lambda p: (root / p).read_text(encoding="utf-8")
v=read("BonsaiLab/ProductionView.swift")
e=read("BonsaiLab/BonsaiEngine.swift")
s=read("BonsaiLab/LocalOpenAIServer.swift")
g=read("BonsaiLab/M5RuntimeGovernor.swift")
w=read(".github/workflows/build-ios.yml")
assert f'CURRENT_PROJECT_VERSION: "{_current_build}"' in read("project.yml")
assert f'RC126APIStartupLifecycle.begin(build: "{_current_build}")' in v
assert '"build_id": "rc1.26-build106-m5-governor"' in s
assert 'contextParams.n_seq_max = 1' in e
assert 'private let textKVReuseEnabled = false' in e
assert 'Build105StartupRecovery.apply()' in v
assert 'Build94BatchExperiment.select(context: context)' in v
assert 'M5RuntimeGovernor.decide(' in v
assert 'apiRuntime.batch = governorDecision.profile.batch' in v
assert 'apiRuntime.ubatch = governorDecision.profile.ubatch' in v
assert '"selection_boundary": "llama_context_creation"' in g
assert '"mid_request_batch_switch_supported": false' in g
assert '/debug/build106/governor' in s
assert f'path: build/BonsaiLab-v1-RC1.26-Build{_current_build}-B16-Prefill-TestKit.zip' in w
assert f'BonsaiLab-v1-RC1.26-build{_current_build}-b16-prefill-unsigned.ipa' in w
assert 'lab-v1-rc1-26-build106-m5-governor' in w
print("PASS Build106 runtime integration and Build105 safety inheritance")
