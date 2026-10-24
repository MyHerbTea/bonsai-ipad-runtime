import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))

class SamplingPatchTests(unittest.TestCase):
    def test_tls_flush_precedes_existing_final_barrier(self):
        import rc126_build121_patch_cpu_timing as timing
        import rc126_build122_patch_sampling as sampling
        native=Path(os.environ.get('BONSAI_PRISM_TEST_DIR','D:/codexSpace/iPad27B/native-prism'))
        if not native.exists():self.skipTest('pinned native required')
        raw=subprocess.check_output(['git','-C',str(native),'show','HEAD:ggml/src/ggml-cpu/ggml-cpu.c'],text=True,encoding='utf-8')
        timed=timing.instrument(raw);result=sampling.instrument_cpu(timed)
        self.assertEqual(result.count('ggml_barrier(state->threadpool);'),raw.count('ggml_barrier(state->threadpool);'))
        self.assertIn('BonsaiNativeCPUSamplingLeave();\n    ggml_barrier(state->threadpool);',result)
        self.assertEqual(result.count('BonsaiNativeCPUSamplingEnter(state->ith);'),1)
    def test_baseline_sample_clone_preserves_original_math_and_counter_position(self):
        path=ROOT/'tools/rc126_build122_patch_sampling.py'
        self.assertTrue(path.exists(),'Build122 sampling patch missing')
        spec=importlib.util.spec_from_file_location('sampling_patch',path)
        patch=importlib.util.module_from_spec(spec);spec.loader.exec_module(patch)
        native=Path(os.environ.get('BONSAI_PRISM_TEST_DIR','D:/codexSpace/iPad27B/native-prism'))
        if not native.exists():self.skipTest('pinned native required')
        raw=subprocess.check_output(['git','-C',str(native),'show','HEAD:ggml/src/ggml-cpu/quants.c'],text=True,encoding='utf-8')
        import rc126_build118_patch_cpu_prefill as old
        # Use real local patched function or synthesize only the original Build118 entry hook.
        start=raw.index('void ggml_vec_dot_ptq1_0_q8_0_generic(')
        at=raw.index('    static const uint8_t pow3[6]',start)
        hook='''    const int bonsai_flags = atomic_load_explicit(&bonsai_cpu_flags, memory_order_relaxed);
    if (bonsai_flags >= 0) {
        const int arm = (bonsai_flags & 16) ? 2 : (bonsai_flags & 8) ? 1 : 0;
        atomic_fetch_add_explicit(&bonsai_cpu_calls[arm], 1, memory_order_relaxed);
        if (arm != 0) { *s = bonsai_cpu_dot(n, x, y, arm == 2); return; }
    }

'''
        raw=raw[:at]+hook+raw[at:]
        result=patch.instrument_quants(raw)
        self.assertIn('bonsai_sampled_ptq1_dot',result)
        self.assertIn('atomic_load_explicit(&bonsai_counting_on',result)
        region=result[result.index('// BONSAI_SAMPLING_122'):result.index('\nvoid ggml_vec_dot_q4_0',result.index('// BONSAI_SAMPLING_122'))]
        self.assertEqual(region.count('sumi += d1 * sumi_block;'),2)
        self.assertEqual(region.count('sumf += d0 * sumi;'),2)
        original=result[result.index('void ggml_vec_dot_ptq1_0_q8_0_generic('):]
        self.assertLess(original.index('atomic_fetch_add_explicit'),original.index('if (bonsai_take_sample)'))
        with self.assertRaises(ValueError):patch.instrument_quants(result)

if __name__=='__main__':unittest.main()
