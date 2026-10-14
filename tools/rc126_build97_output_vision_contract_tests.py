#!/usr/bin/env python3
"""Build97 output budget and home Vision selection source contracts.

These tests do not substitute for actual iPad long-output and vision regression.
"""
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
server = (root / "BonsaiLab/LocalOpenAIServer.swift").read_text()
project = (root / "project.yml").read_text()
workflow = (root / ".github/workflows/build-ios.yml").read_text()

assert f'CURRENT_PROJECT_VERSION: "{_current_build}"' in project
assert f'RC126APIStartupLifecycle.begin(build: "{_current_build}")' in view
assert '"build_id": "rc1.26-build106-m5-governor"' in server
assert 'BonsaiBuild97APIMaxOutputTokens' in view
assert '[256, 512, 1024, 2048, 4096, 8192, 16384, 32768]' in view
assert 'maxOutputTokens: apiMaxOutputTokens' in view
assert 'maxOutputTokens: 256' not in view
assert 'max(1, contextWindow - 1)' in server
assert 'min(maxOutputLimit, max(1, requested))' in server
assert 'contextWindow: advertisedContextWindow' in server
assert 'maxOutputLimit: advertisedMaxOutputTokens' in server
assert 'let maxTokens = min(\n            2048,' not in server
assert '?? maxOutputLimit' in server, 'Client omission must inherit configured iPad API ceiling'
assert view.index('Section("模型")') < view.index('Section("MLX Vision Sidecar")') < view.index('Section("图片")')
assert view.index('Section("MLX Vision Sidecar")') < view.index('DisclosureGroup(\n                        "高级与诊断"')
assert view.count('Text("MLX Vision Sidecar Probe")') == 1
assert 'runMLXVisionProbe()' in view and 'runLiveVisionInjection()' in view
assert f'Build{_current_build}-B16-Prefill' in workflow
assert f'build{_current_build}-b16-prefill-unsigned.ipa' in workflow
print("PASS Build97 output budget, homepage MLX Vision placement and release identity contracts")
