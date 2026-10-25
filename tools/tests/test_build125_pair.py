import os,sys,subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))

class PairTests(unittest.TestCase):
    def sources(self):
        native=Path(os.environ.get('BONSAI_PRISM_TEST_DIR','D:/codexSpace/iPad27B/native-prism'))
        q=(native/'ggml/src/ggml-cpu/quants.c').read_text(encoding='utf-8')
        c=(native/'ggml/src/ggml-cpu/ggml-cpu.c').read_text(encoding='utf-8')
        import rc126_build124_patch_sdot as p124
        import rc126_build123_patch_unpack_reuse as p123
        if 'BONSAI_SDOT_124' not in q:q=p124.instrument_quants(q)
        if 'BONSAI_UNPACK_REUSE_123' not in c:c=p123.instrument_cpu(c)
        return q,c
    def test_pair_preserves_single_kernel_and_production_math(self):
        import rc126_build125_patch_sdot_pair as p
        q,c=self.sources()
        if 'BONSAI_SDOT_PAIR_125' in q:self.skipTest('already patched; ARM64 fixture verifies actual code')
        r=p.instrument_quants(q)
        start=q.index('__attribute__((target("dotprod"),noinline)) static void bonsai_sdot_ptq1_dot(')
        end=q.index('// BONSAI_SDOT_124_END',start)
        self.assertIn(q[start:end],r)
        a=q.index('    static const uint8_t pow3[6]',q.index('void ggml_vec_dot_ptq1_0_q8_0_generic('))
        b=q.index('\nvoid ',a)
        self.assertIn(q[a:b],r)
        self.assertIn('BonsaiNativeCPUSDOTPair',r)
        self.assertIn('bonsai_ptq1_off_control(n)',r)
        with self.assertRaises(ValueError):p.instrument_quants(r)
    def test_route_retains_fallback_barriers_and_single_tail(self):
        import rc126_build125_patch_sdot_pair as p
        q,c=self.sources()
        if 'BONSAI_SDOT_PAIR_ROUTE_125' in c:self.skipTest('already patched; actual chunk fixture covers it')
        r=p.instrument_cpu(c)
        self.assertEqual(r.count('ggml_barrier('),c.count('ggml_barrier('))
        self.assertIn('BonsaiNativeCPUSDOTPair(',r)
        self.assertIn('ne11 > 1 && ne11 <= 8',r)
        self.assertIn('bonsai_pair_row + 1 <',r)
        self.assertIn('vec_dot(ne00, &tmp[ir0 - iir0]',r)
        with self.assertRaises(ValueError):p.instrument_cpu(r)
    def test_real_arm64_pair_chunk_parity(self):
        if sys.platform!='darwin' or os.uname().machine!='arm64':
            if os.environ.get('CI'):self.fail('Build125 requires real Apple ARM64 runner; not a skipped gate')
            self.skipTest('actual ARM64 + ASAN/UBSAN gate executes in Apple CI')
        import build125_pair_fixture as f
        f.verify(ROOT,Path(os.environ['BONSAI_PRISM_TEST_DIR']))

if __name__=='__main__':unittest.main()
