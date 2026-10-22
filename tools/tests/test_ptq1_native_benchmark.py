"""PTQ1 native candidate tests: codec arithmetic, tail rows, patched source contracts."""
import importlib.util
import math
import os
import shutil
import subprocess
import tempfile
import sys
from pathlib import Path
import random
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / 'tools/rc126_build114_patch_prism_ptq1_benchmark.py'

class NativeBenchmarkTests(unittest.TestCase):
    def test_patch_and_abi_exist(self):
        self.assertTrue(PATCH.exists(), 'native strategy implementation missing')
        header = (ROOT / 'BonsaiLab/BenchmarkNativeBridge.h').read_text(encoding='utf-8-sig')
        for name in ('BonsaiBenchmarkConfigure', 'BonsaiBenchmarkCapabilities', 'BonsaiBenchmarkCounter'):
            self.assertIn(name, header)

    def test_collapsed_byte_dot_matches_reference(self):
        rng = random.Random(114)
        for byte in range(256):
            for _ in range(4):
                y = [rng.uniform(-2, 2) for _ in range(5)]
                trits = [(((byte * 3**n) & 255) * 3 >> 8) - 1 for n in range(5)]
                reference = sum(t * v for t, v in zip(trits, y))
                c = [y[n] - 3*y[n+1] for n in range(4)] + [y[4]]
                collapsed = sum(math.floor(3**(n+1) * byte/256) * c[n] for n in range(5)) - sum(y)
                self.assertAlmostEqual(reference, collapsed, places=11)

    def test_five_row_dispatch_has_no_missing_or_out_of_bounds_rows(self):
        for rows in (1, 4, 5, 6, 127, 128, 129, 5120, 18432):
            visited = []
            for group in range((rows + 4)//5):
                for row in range(5):
                    i = group*5 + row
                    if i < rows:
                        visited.append(i)
            self.assertEqual(visited, list(range(rows)))
            self.assertLessEqual((rows + 4)//5, (rows + 3)//4)

    def test_actual_native_control_cpp(self):
        compiler = shutil.which('clang++') or shutil.which('c++') or shutil.which('g++')
        if not compiler:
            self.skipTest('C++ compiler unavailable; macOS CI executes actual native control')
        sys.path.insert(0, str(ROOT / 'tools'))
        spec = importlib.util.spec_from_file_location('ptq1_native_patch', PATCH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        preamble = r"""
#include <atomic>
#include <chrono>
#include <thread>
#include <cstdint>
#include <cassert>
enum { GGML_TYPE_PTQ1_0, GGML_TYPE_F32 };
struct ggml_tensor { int type; int64_t ne[4]; uint64_t nb[4]; ggml_tensor * src[2]; };
bool ggml_is_transposed(const ggml_tensor *) { return false; }
std::atomic<uint64_t> bonsai_ptq1_route_selected_count{0};
std::atomic<uint64_t> bonsai_ptq1_pipeline_ready_count{0};
std::atomic<uint64_t> bonsai_ptq1_dispatch_enqueued_count{0};
std::atomic<uint64_t> bonsai_ptq1_fallback_count{0};
extern "C" {
""" + module.DECLARATIONS + '\n}\n'
        checks = r"""
int main() {
    assert(BonsaiNativeBenchmarkConfigure(1) == 0);
    assert(BonsaiNativeBenchmarkConfigure(-2) == 0);
    assert(BonsaiNativeBenchmarkConfigure(8) == 0);
    BonsaiNativeBenchmarkPublishCapabilities(7);
    assert(BonsaiNativeBenchmarkConfigure(0) == 1);
    assert(!BonsaiNativeBenchmarkTensorEnabled(true));
    for (int i=0; i<10; ++i) {
        assert(BonsaiNativeBenchmarkConfigure(1) == 1);
        assert(BonsaiNativeBenchmarkTensorEnabled(false));
        assert(BonsaiNativeBenchmarkConfigure(0) == 1);
        assert(!BonsaiNativeBenchmarkTensorEnabled(true));
    }
    ggml_tensor weight{}, input{}, output{};
    weight.type = GGML_TYPE_PTQ1_0; weight.ne[0]=128; weight.ne[1]=6;
    input.type = output.type = GGML_TYPE_F32; input.ne[1]=1;
    input.nb[0]=output.nb[0]=sizeof(float);
    output.src[0]=&weight; output.src[1]=&input;
    assert(BonsaiNativeBenchmarkConfigure(2) == 1);
    assert(BonsaiNativeBenchmarkFusedEnabled(&output));
    input.ne[1]=2; assert(!BonsaiNativeBenchmarkFusedEnabled(&output));
    input.ne[1]=1;
    assert(BonsaiNativeBenchmarkConfigure(-1) == 1);
    assert(!BonsaiNativeBenchmarkFusedEnabled(&output));
    assert(BonsaiNativeBenchmarkTensorEnabled(true));
    assert(!BonsaiNativeBenchmarkTensorEnabled(false));
    BonsaiNativeBenchmarkIncrement(6);
    assert(BonsaiNativeBenchmarkConfigure(0) == 0);
    BonsaiNativeBenchmarkIncrement(7);
    assert(BonsaiNativeBenchmarkConfigure(0) == 1);
    BonsaiNativeBenchmarkIncrement(6); BonsaiNativeBenchmarkIncrement(8);
    assert(BonsaiNativeBenchmarkConfigure(7) == 1);
    assert(BonsaiNativeBenchmarkCounter(6) == 2);
    assert(BonsaiNativeBenchmarkCounter(7) == 1);
    assert(BonsaiNativeBenchmarkCounter(8) == 1);
    BonsaiNativeBenchmarkFusedFailed();
    assert(!(BonsaiNativeBenchmarkCapabilities() & 2));
    assert(BonsaiNativeBenchmarkConfigure(2) == 0);
    assert(BonsaiNativeBenchmarkCounter(9) == 1);
    BonsaiNativeBenchmarkTensorFailed();
    assert(!BonsaiNativeBenchmarkTensorSourceAvailable());
    assert(BonsaiNativeBenchmarkConfigure(1) == 0);
    assert(BonsaiNativeBenchmarkConfigure(4) == 1);
    assert(BonsaiNativeBenchmarkCounter(-1) == 0);
    assert(BonsaiNativeBenchmarkCounter(10) == 0);
}
"""
        (ROOT / 'deliveries').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='ptq1-native-', dir=ROOT / 'deliveries') as folder:
            cpp = Path(folder) / 'control.cpp'
            binary = Path(folder) / ('control.exe' if os.name == 'nt' else 'control')
            cpp.write_text(preamble + module.CONTROL + checks, encoding='utf-8')
            subprocess.run([compiler, '-std=c++17', '-pthread', str(cpp), '-o', str(binary)], check=True, capture_output=True, text=True)
            subprocess.run([str(binary)], check=True, capture_output=True, text=True)

    def test_patched_dependency_contracts(self):
        metal = Path(os.environ.get('BONSAI_PRISM_TEST_DIR', str(ROOT / 'deliveries/prism-source'))) / 'ggml/src/ggml-metal'
        if not metal.exists():
            self.skipTest('pinned patched Prism not present; set BONSAI_PRISM_TEST_DIR')
        ops = (metal / 'ggml-metal-ops.cpp').read_text(encoding='utf-8-sig')
        self.assertIn('BONSAI_PTQ1_BENCHMARK_114', ops)
        self.assertIn('BonsaiNativeBenchmarkConfigure', ops)
        self.assertIn('props_dev->has_tensor_benchmark', ops)
        self.assertIn('BonsaiNativeBenchmarkTensorEnabled', ops)
        context = (metal / 'ggml-metal-context.m').read_text(encoding='utf-8-sig')
        self.assertIn('addCompletedHandler', context)
        self.assertIn('MTLCommandBufferStatusCompleted', context)
        self.assertIn('BonsaiNativeBenchmarkIncrement(7)', context)
        self.assertIn('BonsaiNativeBenchmarkIncrement(8)', context)
        kernel = (metal / 'kernels/mul_mv.metal').read_text(encoding='utf-8-sig')
        self.assertIn('kernel_mul_mv_ptq1_0_f32_bonsai_r5', kernel)
        self.assertIn('kernel_mul_mv_ptq1_0_f32_impl<5,', kernel)
        self.assertNotIn('kernel_mul_mv_ptq1_0_f32_bonsai_r5_impl', kernel)
        self.assertTrue('nr0 != 5 || first_row + row < args.ne01' in kernel)
        device = (metal / 'ggml-metal-device.m').read_text(encoding='utf-8-sig')
        self.assertIn('dev->props.has_tensor_benchmark = dev->props.has_tensor', device)
        self.assertIn('fallback removeObjectForKey:@"GGML_METAL_HAS_BONSAI_PTQ1_TENSOR"', device)
        self.assertIn('BonsaiNativeBenchmarkTensorSourceAvailable()', device)

if __name__ == '__main__':
    unittest.main()
