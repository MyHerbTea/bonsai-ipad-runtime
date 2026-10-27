"""Fail-closed structural checks for request-level Build129-derived profile evidence.

This checks supplied observations, not their provenance or correctness. A passing
result is necessary, never sufficient, for a valid device measurement.
"""
import math
import re

MODEL_SHA = '53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3'
RUNTIME = dict(context=16384, batch=8, ubatch=8, kv_k='Q8_0', kv_v='Q8_0', gpu_layers=56, threads=6, threads_batch=6, kv_unified=True, offload_kqv=True, flash_attention=True, text_kv_reuse=False, op_offload=True, mmap=True, sequence_max=1, swa_full=False, metal_tensor_disabled=True)
REQUIRED_TRUE = ('exclusive', 'gpu_drained_before', 'gpu_drained_after', 'counters_available', 'counters_reset', 'counters_disabled_after', 'completed', 'cpu_prefill_available', 'gpu_prefill_available', 'instrumentation_overhead_checked')

def validate(evidence, expected_source_git_sha=None):
    if not isinstance(evidence, dict):
        return ['evidence']
    errors = [key for key in REQUIRED_TRUE if evidence.get(key) is not True]
    if not re.fullmatch(r'[0-9a-f]{40}', str(evidence.get('source_git_sha', ''))) or (expected_source_git_sha is not None and evidence.get('source_git_sha') != expected_source_git_sha):
        errors.append('source_git_sha')
    if evidence.get('model_sha256') != MODEL_SHA:
        errors.append('model_sha256')
    if not evidence.get('context_id_before') or evidence.get('context_id_before') != evidence.get('context_id_after'):
        errors.append('context_identity')
    if not evidence.get('request_id') or evidence.get('request_id') != evidence.get('profile_request_id'):
        errors.append('request_identity')
    before = evidence.get('actual_before'); after = evidence.get('actual_after')
    if not isinstance(before, dict) or not isinstance(after, dict) or before != after or any(type(before.get(k)) is not type(v) or before.get(k) != v or type(after.get(k)) is not type(v) or after.get(k) != v for k, v in RUNTIME.items()):
        errors.append('runtime_configuration')
    ms = evidence.get('prefill_ms')
    if type(ms) not in (float, int) or not math.isfinite(ms) or ms <= 0:
        errors.append('prefill_ms')
    return errors
