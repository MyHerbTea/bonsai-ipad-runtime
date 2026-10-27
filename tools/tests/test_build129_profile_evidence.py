import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / 'tools' / 'build129_profile_evidence.py'

class ProfileEvidenceTests(unittest.TestCase):
    def load(self):
        self.assertTrue(MODULE.is_file(), 'profile evidence validator missing')
        spec = importlib.util.spec_from_file_location('profile_evidence', MODULE)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def evidence(self):
        config = dict(context=16384, batch=8, ubatch=8, kv_k='Q8_0', kv_v='Q8_0', gpu_layers=56, threads=6, threads_batch=6, kv_unified=True, offload_kqv=True, flash_attention=True, text_kv_reuse=False, op_offload=True, mmap=True, sequence_max=1, swa_full=False, metal_tensor_disabled=True)
        return dict(source_git_sha='a'*40, model_sha256='53107f530aa52eb00912263ab1ee29bd199261c87cd7b4ad4ca1318c1fe33ee3', request_id='r1', context_id_before='ctx', context_id_after='ctx', actual_before=config, actual_after=copy.deepcopy(config), exclusive=True, gpu_drained_before=True, gpu_drained_after=True, counters_available=True, counters_reset=True, counters_disabled_after=True, completed=True, profile_request_id='r1', prefill_ms=1000.0, cpu_prefill_available=True, gpu_prefill_available=True, instrumentation_overhead_checked=True)

    def test_complete_same_context_evidence_is_accepted(self):
        self.assertEqual(self.load().validate(self.evidence()), [])

    def test_unproven_isolation_or_drain_is_rejected(self):
        validate = self.load().validate
        for field in ('exclusive', 'gpu_drained_before', 'gpu_drained_after', 'counters_available', 'counters_reset', 'counters_disabled_after', 'completed', 'cpu_prefill_available', 'gpu_prefill_available', 'instrumentation_overhead_checked'):
            e = self.evidence(); e[field] = False
            self.assertIn(field, validate(e), field)

    def test_context_request_and_configuration_mismatch_are_rejected(self):
        validate = self.load().validate
        for field, value, expected in [('context_id_after', 'different', 'context_identity'), ('profile_request_id', 'other', 'request_identity'), ('model_sha256', '0'*64, 'model_sha256')]:
            e = self.evidence(); e[field] = value
            self.assertIn(expected, validate(e))
        for field, value in [('kv_unified', False), ('batch', 16), ('kv_k', 'Q4_0'), ('threads', 4), ('mmap', False), ('op_offload', False)]:
            e = self.evidence(); e['actual_after'][field] = value
            self.assertIn('runtime_configuration', validate(e))

    def test_unexpected_configuration_change_is_rejected(self):
        e = self.evidence(); e['actual_before']['extra_flag'] = False; e['actual_after']['extra_flag'] = True
        self.assertIn('runtime_configuration', self.load().validate(e))

    def test_source_must_match_the_expected_derived_build(self):
        e = self.evidence()
        self.assertIn('source_git_sha', self.load().validate(e, expected_source_git_sha='b'*40))

    def test_invalid_or_missing_prefill_time_is_rejected(self):
        validate = self.load().validate
        for value in (None, 0, -1, float('nan'), float('inf'), True):
            e = self.evidence(); e['prefill_ms'] = value
            self.assertIn('prefill_ms', validate(e))

if __name__ == '__main__': unittest.main()
