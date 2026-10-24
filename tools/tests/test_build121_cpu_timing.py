import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))


class TimingTests(unittest.TestCase):
    def load_patch(self):
        path = ROOT / 'tools/rc126_build121_patch_cpu_timing.py'
        self.assertTrue(path.exists(), 'Build121 CPU timing patch missing')
        spec = importlib.util.spec_from_file_location('timing_patch', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_real_pinned_graph_keeps_barriers_and_covers_final_node(self):
        module = self.load_patch()
        native = Path(os.environ.get('BONSAI_PRISM_TEST_DIR', 'D:/codexSpace/iPad27B/native-prism'))
        if not native.is_dir():
            self.skipTest('pinned native tree required')
        source = subprocess.check_output(['git', '-C', str(native), 'show', 'HEAD:ggml/src/ggml-cpu/ggml-cpu.c'], text=True, encoding='utf-8')
        result = module.instrument(source)
        self.assertEqual(result.count('ggml_barrier(state->threadpool);'), source.count('ggml_barrier(state->threadpool);'))
        self.assertIn('GGML_HINT_SRC0_IS_HADAMARD', result)
        self.assertIn('node->src[0]->type == GGML_TYPE_PTQ1_0', result)
        self.assertEqual(result.count('bonsai_cpu_time_end(bonsai_timing_category, bonsai_timing_start);'), 2)
        self.assertIn('ggml_barrier(state->threadpool);\n    if (state->ith == 0)', result)
        self.assertIn('state->ith == 0', result)
        with self.assertRaises(ValueError):
            module.instrument(result)

    def test_real_clock_disabled_reset_and_single_leader_accounting(self):
        self.load_patch()
        compiler = shutil.which('clang')
        if not compiler or os.name == 'nt':
            self.skipTest('Apple CI executes C clock test')
        program = r'''
#include <assert.h>
#include <unistd.h>
#include "build121_cpu_timing.h"
int main(void) {
    BonsaiNativeCPUTimeReset();
    assert(bonsai_cpu_time_begin() == 0);
    BonsaiNativeCPUTimeEnable(1);
    uint64_t start = bonsai_cpu_time_begin();
    usleep(5000);
    bonsai_cpu_time_end(0,start);
    BonsaiNativeCPUTimeEnable(0);
    assert(BonsaiNativeCPUTimeCounter(0) >= 1000000);
    assert(BonsaiNativeCPUTimeCounter(4) == 1);
    assert(BonsaiNativeCPUTimeCounter(1) == 0);
    assert(bonsai_cpu_time_begin() == 0);
    bonsai_cpu_time_end(0,0);
    assert(BonsaiNativeCPUTimeCounter(4) == 1);
    BonsaiNativeCPUTimeReset();
    assert(BonsaiNativeCPUTimeCounter(0) == 0);
    assert(BonsaiNativeCPUTimeCounter(4) == 0);
    assert(BonsaiNativeCPUTimeCounter(-1) == 0);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / 'clock.c'
            source.write_text(program, encoding='utf-8')
            subprocess.run([compiler, '-std=c11', '-O2', '-I', str(ROOT / 'tools/native'), str(source), '-o', str(directory/'clock')], check=True, capture_output=True)
            subprocess.run([str(directory/'clock')], check=True, capture_output=True)


if __name__ == '__main__':
    unittest.main()
