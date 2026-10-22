import importlib.util
import os
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))

class ProfilePatchTests(unittest.TestCase):
    def test_patch_has_real_dispatch_and_completion_instrumentation(self):
        script=ROOT/'tools/rc126_build117_patch_profiling.py'
        self.assertTrue(script.exists(), 'Build117 profiling patch missing')
        spec=importlib.util.spec_from_file_location('profiling_patch',script)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertIn('GPUStartTime',module.COMPLETION)
        self.assertIn('GPUEndTime',module.COMPLETION)
        self.assertIn('memory_order',module.CONTROL)
        self.assertIn('nr0 == 4',module.DISPATCH)
        self.assertIn('nr0 == 5',module.DISPATCH)

    def test_patched_upstream_exposes_profile_abi(self):
        root=os.environ.get('BONSAI_PRISM_TEST_DIR')
        if not root:self.skipTest('set BONSAI_PRISM_TEST_DIR after applying all pinned patches')
        root=Path(root)
        code=(root/'ggml/src/ggml-metal/ggml-metal-ops.cpp').read_text()
        header=(root/'ggml/src/ggml-metal/ggml-metal-device.h').read_text()
        for name in ['BonsaiNativeProfileCounter','BonsaiNativeProfileAdd','BonsaiNativeProfileReset']:
            self.assertIn(name,code);self.assertIn(name,header)

    def test_actual_atomic_profile_control(self):
        compiler=shutil.which('clang++') or shutil.which('g++') or shutil.which('c++')
        if not compiler:self.skipTest('C++ compiler unavailable; run on Apple CI')
        import rc126_build117_patch_profiling as p
        source='#include <atomic>\n#include <cstdint>\n#include <thread>\n#include <cassert>\n'+p.CONTROL+r'''
int main() {
    BonsaiNativeProfileReset();
    BonsaiNativeProfileAdd(0, 3);
    assert(BonsaiNativeProfileCounter(0) == 0);
    BonsaiNativeProfileEnable(1);
    std::thread a([] { for(int i=0;i<10000;i++) BonsaiNativeProfileAdd(0,1); });
    std::thread b([] { for(int i=0;i<10000;i++) BonsaiNativeProfileAdd(0,1); });
    a.join(); b.join();
    assert(BonsaiNativeProfileCounter(0) == 20000);
    BonsaiNativeProfileAdd(-1, 1); BonsaiNativeProfileAdd(9,1);
    assert(BonsaiNativeProfileCounter(9) == 0);
    BonsaiNativeProfileReset(); assert(BonsaiNativeProfileCounter(0) == 0);
}
'''
        with tempfile.TemporaryDirectory() as folder:
            cpp=Path(folder)/'profile.cpp';binary=Path(folder)/('profile.exe' if os.name=='nt' else 'profile')
            cpp.write_text(source,encoding='utf-8')
            subprocess.run([compiler,'-std=c++17','-pthread',str(cpp),'-o',str(binary)],check=True,capture_output=True)
            subprocess.run([str(binary)],check=True,capture_output=True)

if __name__=='__main__':unittest.main()
