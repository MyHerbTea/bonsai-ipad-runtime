"""Apply after Build117 to pinned Prism; production flags remain disabled."""
from pathlib import Path
import argparse
from rc126_build113_patch_prism_ptq1_tensorops import BASE_SHA, run_git, replace_once, run_diff_check

def lookup_table():
    return '\n'.join('{' + ','.join(str(((((byte * 3**n) & 255) * 3) >> 8) - 1) for n in range(5)) + '},' for byte in range(256)) + '\n'

def apply(root):
    if run_git(root, 'rev-parse', 'HEAD') != BASE_SHA: raise SystemExit('wrong Prism base')
    cpu = root/'ggml/src/ggml-cpu'
    source = cpu/'quants.c'
    if 'BONSAI_CPU_PREFILL_118' in source.read_text(): raise SystemExit('Build118 already applied')
    (cpu/'build118_ptq1_cpu.h').write_text((Path(__file__).parent/'native/build118_ptq1_cpu.h').read_text(),encoding='utf-8')
    (cpu/'build118_ptq1_lut.inc').write_text(lookup_table(),encoding='utf-8')
    replace_once(source, '#define GROUP_MAX_EPS 1e-15f',
                 '// BONSAI_CPU_PREFILL_118\n#include "build118_ptq1_cpu.h"\n\n#define GROUP_MAX_EPS 1e-15f')
    code=source.read_text(encoding='utf-8')
    start=code.index('void ggml_vec_dot_ptq1_0_q8_0_generic(')
    at=code.index('    static const uint8_t pow3[6]',start)
    branch='''    const int bonsai_flags = atomic_load_explicit(&bonsai_cpu_flags, memory_order_relaxed);
    if (bonsai_flags >= 0) {
        const int arm = (bonsai_flags & 16) ? 2 : (bonsai_flags & 8) ? 1 : 0;
        atomic_fetch_add_explicit(&bonsai_cpu_calls[arm], 1, memory_order_relaxed);
        if (arm != 0) { *s = bonsai_cpu_dot(n, x, y, arm == 2); return; }
    }

'''
    source.write_text(code[:at]+branch+code[at:],encoding='utf-8')
    ops=root/'ggml/src/ggml-metal/ggml-metal-ops.cpp'
    replace_once(ops, 'static std::atomic<int32_t> bonsai_benchmark_flags{-1};',
        'extern "C" uint32_t BonsaiNativeCPUCapabilities(void);\nextern "C" void BonsaiNativeCPUConfigure(int);\nextern "C" void BonsaiNativeCPUBeginRequest(void);\nstatic std::atomic<int32_t> bonsai_benchmark_flags{-1};')
    replace_once(ops, '    if (flags < -1 || flags > 7) return 0;',
        '    if (flags < -1 || flags > 31 || (flags >= 0 && (flags & 24) == 24)) return 0;')
    replace_once(ops, '    return bonsai_benchmark_caps.load(std::memory_order_acquire);',
        '    return bonsai_benchmark_caps.load(std::memory_order_acquire) | BonsaiNativeCPUCapabilities();')
    replace_once(ops, '    bonsai_benchmark_flags.store(flags, std::memory_order_release);',
        '    BonsaiNativeCPUConfigure(flags);\n    bonsai_benchmark_flags.store(flags, std::memory_order_release);')
    replace_once(ops, 'void BonsaiNativeBenchmarkBeginRequest(void) {',
        'void BonsaiNativeBenchmarkBeginRequest(void) {\n    BonsaiNativeCPUBeginRequest();')
    run_diff_check(root)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);apply(p.parse_args().root)
