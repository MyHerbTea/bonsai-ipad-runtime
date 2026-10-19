#!/usr/bin/env python3
from pathlib import Path
import ast
ROOT=Path(__file__).resolve().parent
source=(ROOT/'ptq1_tensorops_ab.py').read_text(encoding='utf-8')
ast.parse(source)
for needle in (
    'source_git_sha','TestKitIdentity.json has no source_git_sha','PTQ1_0',
    'native_context_batch','native_context_ubatch','backend_evidence_valid',
    'phase2d_launch_arm','ptq1_tensorops_trace','route_selected_delta',
    'pipeline_ready_delta','dispatch_enqueued_delta','fallback_delta',
    'dispatch_completion_proof','prompt_tokens==target','completion_tokens==MAX_TOKENS',
    'prefill_tokens_per_second','decode_tokens_per_second','metal_working_set_headroom_bytes',
    'SHA256_MANIFEST.json','Previous ZIP prompt bank hash does not match result.json',
    'candidate_route_verified','target_tokens','ttft_reconstruction_error_ms',
    'thermal_ok','Thermal state is missing, unstable, or differs between arms',
    'allocated>0','M5_PERFORMANCE_GAIN_VERIFIED',
    'CANDIDATE_NO_GAIN','BLOCKED_NEEDS_ENGINE_EVIDENCE','REPEATS = 3','MAX_TOKENS = 128'
):
    assert needle in source, f'missing A/B contract: {needle}'
ps=(ROOT/'run_ptq1_tensorops_ab.ps1').read_text(encoding='utf-8')
assert 'BASELINE' in ps and 'CANDIDATE' in ps and 'BONSAI_API_KEY' in ps
assert 'RUN_PTQ1_TENSOROPS_AB.cmd' in (ROOT/'README.txt').read_text(encoding='utf-8')
print('PTQ1_TENSOROPS_AB_TESTKIT_CONTRACT: PASS')
