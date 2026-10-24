"""Apply after121; original baseline math/order retained in unsampled and sampled clones."""
from pathlib import Path
import argparse
from rc126_build113_patch_prism_ptq1_tensorops import BASE_SHA,run_git,run_diff_check

def instrument_quants(source):
    if 'BONSAI_SAMPLING_122' in source: raise ValueError('already sampled')
    start=source.index('void ggml_vec_dot_ptq1_0_q8_0_generic(')
    end=source.index('\nvoid ',start+5)
    original=source[start:end]
    control=original.index('    const int bonsai_flags')
    math=original.index('    static const uint8_t pow3[6]')
    clone=original[:control]+original[math:]
    clone=clone.replace('void ggml_vec_dot_ptq1_0_q8_0_generic(', 'static void bonsai_sampled_ptq1_dot(',1)
    clone=clone.replace('    float sumf = 0.0f;','    uint64_t unpack_ticks=0,dot_ticks=0;\n    float sumf = 0.0f;',1)
    clone=clone.replace('        int o = 0;','        int o = 0;\n        const uint64_t unpack_start=bonsai_sample_clock();',1)
    clone=clone.replace('        assert(o == QK_PTQ1_0);','        assert(o == QK_PTQ1_0);\n        const uint64_t dot_start=bonsai_sample_clock();',1)
    clone=clone.replace('        sumf += d0 * sumi;','        sumf += d0 * sumi;\n        const uint64_t dot_end=bonsai_sample_clock();\n        unpack_ticks+=dot_start-unpack_start;dot_ticks+=dot_end-dot_start;',1)
    clone=clone.replace('    *s = sumf;','    bonsai_sample_tls.unpack_ticks+=unpack_ticks;bonsai_sample_tls.dot_ticks+=dot_ticks;bonsai_sample_tls.blocks+=(uint64_t)nb;\n    *s = sumf;',1)
    original=original.replace('        atomic_fetch_add_explicit(&bonsai_cpu_calls[arm], 1, memory_order_relaxed);','        if (atomic_load_explicit(&bonsai_counting_on,memory_order_relaxed))\n            atomic_fetch_add_explicit(&bonsai_cpu_calls[arm], 1, memory_order_relaxed);',1)
    original=original.replace('    static const uint8_t pow3[6]','    const int bonsai_take_sample = bonsai_flags == 0 && bonsai_sample_next(n);\n    if (bonsai_take_sample) { bonsai_sampled_ptq1_dot(n,s,bs,vx,bx,vy,by,nrc); return; }\n\n    static const uint8_t pow3[6]',1)
    return source[:start]+'// BONSAI_SAMPLING_122\n'+clone+'\n'+original+source[end:]

def instrument_cpu(s):
    start=s.index('static thread_ret_t ggml_graph_compute_thread(void * data) {')
    end=s.index('\n#ifndef GGML_USE_OPENMP',s.index('\n    return 0;\n}',start))
    body=s[start:end]
    enter='    const struct ggml_cplan  * cplan  = tp->cplan;'
    leave='    ggml_barrier(state->threadpool);\n    if (state->ith == 0)'
    assert body.count(enter)==1 and body.count(leave)==1
    body=body.replace(enter,enter+'\n    BonsaiNativeCPUSamplingEnter(state->ith);',1)
    body=body.replace(leave,'    BonsaiNativeCPUSamplingLeave();\n'+leave,1)
    return s[:start]+body+s[end:]

def apply(root):
    if run_git(root,'rev-parse','HEAD')!=BASE_SHA:raise ValueError('wrong Prism base')
    cpu=root/'ggml/src/ggml-cpu'
    p=cpu/'quants.c';s=instrument_quants(p.read_text(encoding='utf-8'))
    s=s.replace('#include "build118_ptq1_cpu.h"','#include "build118_ptq1_cpu.h"\n#include "build122_sampling.h"',1)
    p.write_text(s,encoding='utf-8')
    (cpu/'build122_sampling.h').write_text((Path(__file__).parent/'native/build122_sampling.h').read_text(encoding='utf-8'),encoding='utf-8')
    p=cpu/'build121_cpu_timing.h';s=p.read_text(encoding='utf-8')
    s='void BonsaiNativeCPUSamplingPhase(int);\nvoid BonsaiNativeCPUSamplingEnter(int);\nvoid BonsaiNativeCPUSamplingLeave(void);\n'+s
    s=s.replace('    atomic_store_explicit(&bonsai_cpu_time_enabled, enabled != 0, memory_order_release);','    BonsaiNativeCPUSamplingPhase(enabled);\n    atomic_store_explicit(&bonsai_cpu_time_enabled, enabled != 0, memory_order_release);',1)
    p.write_text(s,encoding='utf-8')
    p=cpu/'ggml-cpu.c';s=p.read_text(encoding='utf-8')
    p.write_text(instrument_cpu(s),encoding='utf-8')
    run_diff_check(root)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);apply(p.parse_args().root)
