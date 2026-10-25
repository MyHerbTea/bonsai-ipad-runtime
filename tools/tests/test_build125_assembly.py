import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def fixture():
    s="00000100 <_bonsai_sdot_ptq1_dot>:\n 100: sdot v0.4s, v1.16b, v2.16b\n 104: b.ne 0x100\n 108: ret\n00000200 <_ggml_vec_dot_ptq1_0_q8_0>:\n 200: smull v0.8h, v1.8b, v2.8b\n 204: ret\n00000300 <_BonsaiNativeCPUSDOTPair>:\n"
    address=0x300
    for k in range(4):
        for instruction in ['ldp q16, q17, [x5, #'+str(k*34+2)+']','sdot v0.4s, v1.16b, v16.16b','sdot v0.4s, v2.16b, v17.16b','sdot v3.4s, v4.16b, v16.16b','sdot v3.4s, v5.16b, v17.16b']:
            s+=f' {address:x}: {instruction}\n';address+=4
    return s+f' {address:x}: b.ne 0x300\n {address+4:x}: ret\n'

class AssemblyTests(unittest.TestCase):
    def test_proves_reuse_and_rejects_reload_or_stack(self):
        from build125_inspect_assembly import inspect
        s=fixture();r=inspect(s)
        self.assertEqual(r['pair']['shared_q8_load_values'],8)
        self.assertEqual(r['pair']['sdot'],16)
        with self.assertRaises(ValueError):inspect(s.replace('sdot v3.4s, v4.16b, v16.16b','sdot v3.4s, v4.16b, v18.16b'))
        with self.assertRaises(ValueError):inspect(s.replace('ldp q16, q17, [x5, #2]','ldp q16, q17, [sp, #2]'))
        with self.assertRaises(ValueError):inspect(s.replace('b.ne 0x300','bl 0x100'))
if __name__=='__main__':unittest.main()
