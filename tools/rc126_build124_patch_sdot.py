"""Apply after123: preserve baseline arithmetic except each integer dot."""
from pathlib import Path
import argparse
from rc126_build113_patch_prism_ptq1_tensorops import BASE_SHA,run_git,replace_once,run_diff_check

ROUTE='#if BONSAI_CPU_SDOT\n    if (bonsai_flags == 64) { bonsai_sdot_ptq1_dot(n,s,bs,vx,bx,vy,by,nrc); return; }\n#endif\n'

def instrument_quants(source):
    if 'BONSAI_SDOT_124' in source:raise ValueError('already patched124')
    start=source.index('void ggml_vec_dot_ptq1_0_q8_0_generic(')
    end=source.index('\nvoid ',start+5)
    original=source[start:end]
    control=original.index('    const int bonsai_flags')
    math=original.index('    static const uint8_t pow3[6]')
    clone=original[:control]+original[math:]
    clone=clone.replace('void ggml_vec_dot_ptq1_0_q8_0_generic(',
        '__attribute__((target("dotprod"),noinline)) static void bonsai_sdot_ptq1_dot(',1)
    old='            int sumi_block = 0;\n            for (int b = 0; b < 32; ++b) {\n                sumi_block += (int) q[k*32 + b] * (int) yb->qs[b];\n            }'
    new='            int32x4_t dot = vdupq_n_s32(0);\n            dot = vdotq_s32(dot,vld1q_s8(q+k*32),vld1q_s8(yb->qs));\n            dot = vdotq_s32(dot,vld1q_s8(q+k*32+16),vld1q_s8(yb->qs+16));\n            const int sumi_block = vaddvq_s32(dot);'
    if clone.count(old)!=1:raise ValueError('unexpected baseline dot')
    clone=clone.replace(old,new,1)
    anchor='    const int bonsai_flags = atomic_load_explicit(&bonsai_cpu_flags, memory_order_relaxed);'
    if original.count(anchor)!=1:raise ValueError('unexpected baseline control')
    original=original.replace(anchor,anchor+'\n'+ROUTE,1)
    return source[:start]+'// BONSAI_SDOT_124\n#if BONSAI_CPU_SDOT\n'+clone+'\n#endif\n// BONSAI_SDOT_124_END\n'+original+source[end:]

def apply(root):
    if run_git(root,'rev-parse','HEAD')!=BASE_SHA:raise ValueError('wrong Prism base')
    cpu=root/'ggml/src/ggml-cpu'
    p=cpu/'quants.c';p.write_text(instrument_quants(p.read_text(encoding='utf-8')),encoding='utf-8')
    (cpu/'build124_sdot.h').write_text((Path(__file__).parent/'native/build124_sdot.h').read_text(encoding='utf-8'),encoding='utf-8')
    replace_once(cpu/'build118_ptq1_cpu.h','#include <stdint.h>','#include <stdint.h>\n#include "build124_sdot.h"')
    replace_once(cpu/'build118_ptq1_cpu.h','return 32u | 8u | (BONSAI_CPU_NEON ? 16u : 0u);',
        'return 32u | 8u | (BONSAI_CPU_NEON ? 16u : 0u) | (bonsai_sdot_supported() ? 64u : 0u);')
    replace_once(cpu/'build118_ptq1_cpu.h','    atomic_store_explicit(&bonsai_cpu_flags, flags, memory_order_release);',
        '    if (flags==64 && !bonsai_sdot_supported()) flags=-1;\n    atomic_store_explicit(&bonsai_cpu_flags, flags, memory_order_release);')
    replace_once(root/'ggml/src/ggml-metal/ggml-metal-ops.cpp',
        'if (flags != 32 && (flags < -1 || flags > 31 || (flags >= 0 && (flags & 24) == 24))) return 0;',
        'if (flags != 32 && flags != 64 && (flags < -1 || flags > 31 || (flags >= 0 && (flags & 24) == 24))) return 0;')
    run_diff_check(root)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);apply(p.parse_args().root)
