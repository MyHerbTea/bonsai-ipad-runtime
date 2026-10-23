"""Device-observed Apple M5 GPU name and preserved production placement."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class IPadBenchmarkAdmissionTests(unittest.TestCase):
    def test_start_preserves_existing_gpu_placement(self):
        engine = (ROOT / 'BonsaiLab/BonsaiEngine.swift').read_text(encoding='utf-8')
        start = engine[engine.index('    func benchmarkStart('):engine.index('    func benchmarkConfigure(')]
        self.assertNotIn('appliedRuntime.gpuLayers >= 99', start,
                         '56-layer production placement must not be rejected by an arbitrary full-offload request')
        self.assertIn('BenchmarkModelAdmission.accepts', start)

    def test_actual_native_device_name_parser(self):
        compiler = shutil.which('clang++') or shutil.which('c++') or shutil.which('g++')
        prism = Path(os.environ.get('BONSAI_PRISM_TEST_DIR', str(ROOT / 'deliveries/prism-source')))
        metal = prism / 'ggml/src/ggml-metal'
        if not (metal / 'ggml-metal-device.m').exists():
            self.skipTest('pinned patched Prism required')
        source = (metal / 'ggml-metal-device.m').read_text(encoding='utf-8-sig')
        self.assertTrue('BONSAI_IPAD_GPU_NAME_116' in source, 'iPad GPU name patch missing')
        if not compiler:
            self.skipTest('macOS CI executes the actual native parser')
        header = (metal / 'ggml-metal-device.h').read_text(encoding='utf-8-sig')
        enum_start = header.index('enum ggml_metal_device_id {')
        enum_end = header.index('};', enum_start) + 2
        table_start = source.rfind('static const struct {', 0, source.index('k_metal_devices[]'))
        table_end = source.index('const char * ggml_metal_device_id_token', table_start)
        actual = source[table_start:table_end]
        checks = r'''
int main() {
    assert(ggml_metal_device_id_parse("Apple M5 GPU") == GGML_METAL_DEVICE_M5);
    assert(ggml_metal_device_id_parse("Apple M5") == GGML_METAL_DEVICE_M5);
    assert(ggml_metal_device_id_parse("Apple M5 Pro GPU") == GGML_METAL_DEVICE_M5_PRO);
    assert(ggml_metal_device_id_parse("Apple M1") == GGML_METAL_DEVICE_M1);
    for (const char * name : {"Apple M50 GPU", "Other M5 GPU", "Apple A19 GPU", "Apple M5 GPU extra", "Apple M5 GPU ", "Apple m5 GPU"})
        assert(ggml_metal_device_id_parse(name) == GGML_METAL_DEVICE_GENERIC);
    assert(ggml_metal_device_id_parse(nullptr) == GGML_METAL_DEVICE_GENERIC);
}
'''
        (ROOT / 'deliveries').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='ipad-parser-', dir=ROOT / 'deliveries') as folder:
            cpp = Path(folder) / 'parser.cpp'
            binary = Path(folder) / ('parser.exe' if os.name == 'nt' else 'parser')
            cpp.write_text('#include <cstring>\n#include <cassert>\n#include <initializer_list>\n' + header[enum_start:enum_end] + '\n' + actual + checks, encoding='utf-8')
            subprocess.run([compiler, '-std=c++17', str(cpp), '-o', str(binary)], check=True, capture_output=True, text=True)
            subprocess.run([str(binary)], check=True, capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()
