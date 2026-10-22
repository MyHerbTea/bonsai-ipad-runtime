#!/usr/bin/env python3
"""Apply after Build116 patches, to the same pinned Prism tree. No kernel math changes."""
from pathlib import Path
import argparse
from rc126_build113_patch_prism_ptq1_tensorops import replace_once, run_diff_check

DECLARATIONS = '''
__attribute__((visibility("default"))) uint64_t BonsaiNativeProfileCounter(int index);
__attribute__((visibility("default"))) void BonsaiNativeProfileReset(void);
__attribute__((visibility("default"))) void BonsaiNativeProfileEnable(int enabled);
void BonsaiNativeProfileAdd(int index, uint64_t value);
'''
CONTROL = '''
// BONSAI_PROFILE_117: reset only after the previous context is synchronized.
static std::atomic<uint64_t> bonsai_profile_counts[9]{};
static std::atomic_bool bonsai_profile_enabled{false};
extern "C" uint64_t BonsaiNativeProfileCounter(int index) {
    return index >= 0 && index < 9 ? bonsai_profile_counts[index].load(std::memory_order_acquire) : 0;
}
extern "C" void BonsaiNativeProfileEnable(int enabled) { bonsai_profile_enabled.store(enabled != 0); }
extern "C" void BonsaiNativeProfileReset(void) {
    for (auto & count : bonsai_profile_counts) count.store(0, std::memory_order_release);
}
extern "C" void BonsaiNativeProfileAdd(int index, uint64_t value) {
    if (bonsai_profile_enabled.load(std::memory_order_relaxed) && index >= 0 && index < 9)
        bonsai_profile_counts[index].fetch_add(value, std::memory_order_relaxed);
}
'''
DISPATCH = '''
            if (op->src[0]->type == GGML_TYPE_PTQ1_0) {
                if (pipeline.nr0 == 4) BonsaiNativeProfileAdd(0, 1);
                if (pipeline.nr0 == 5) BonsaiNativeProfileAdd(1, 1);
            }
'''
COMPLETION = '''
            if (completed.GPUEndTime > completed.GPUStartTime && completed.GPUStartTime > 0) {
                BonsaiNativeProfileAdd(6, (uint64_t)((completed.GPUEndTime - completed.GPUStartTime) * 1e9));
                BonsaiNativeProfileAdd(7, 1);
            }
'''

def apply(root):
    metal=root/'ggml/src/ggml-metal'
    ops=metal/'ggml-metal-ops.cpp';header=metal/'ggml-metal-device.h';dev=metal/'ggml-metal-device.m'
    if 'BONSAI_PROFILE_117' in ops.read_text(encoding='utf-8'):raise SystemExit('Build117 patch already applied')
    replace_once(header,'void BonsaiNativeBenchmarkIncrement(int index);','void BonsaiNativeBenchmarkIncrement(int index);\n'+DECLARATIONS)
    replace_once(ops,'static std::atomic<int32_t> bonsai_benchmark_flags{-1};',CONTROL+'\nstatic std::atomic<int32_t> bonsai_benchmark_flags{-1};')
    replace_once(ops,'            if (bonsai_fused_dispatched) BonsaiNativeBenchmarkIncrement(5);',
                 '            if (bonsai_fused_dispatched) BonsaiNativeBenchmarkIncrement(5);\n'+DISPATCH)
    # Every matrix op is counted once, separately from dispatch counts.
    anchor='int ggml_metal_op_mul_mat('
    source=ops.read_text(encoding='utf-8');start=source.index(anchor)
    brace=source.index('    ggml_tensor * op = ctx->node(idx);',start)+len('    ggml_tensor * op = ctx->node(idx);')
    source=source[:brace]+'\n    BonsaiNativeProfileAdd(op->src[1]->ne[1] == 1 ? 4 : 5, 1);\n'+source[brace:]
    ops.write_text(source,encoding='utf-8')
    context=metal/'ggml-metal-context.m'
    replace_once(context,'            BonsaiNativeBenchmarkIncrement(7);',COMPLETION+'            BonsaiNativeBenchmarkIncrement(7);')
    replace_once(context,'    [command commit];','    const uint64_t bonsai_submit_start = clock_gettime_nsec_np(CLOCK_UPTIME_RAW);\n    [command commit];\n    BonsaiNativeProfileAdd(8, clock_gettime_nsec_np(CLOCK_UPTIME_RAW) - bonsai_submit_start);')
    replace_once(context,'#import "ggml-metal-impl.h"','#import "ggml-metal-impl.h"\n#include <time.h>')
    replace_once(ops,'        ggml_metal_encoder_dispatch_threadgroups(enc, nrows, 1, 1, GGML_METAL_FWHT_TG_NT, 1, 1);',
                 '        ggml_metal_encoder_dispatch_threadgroups(enc, nrows, 1, 1, GGML_METAL_FWHT_TG_NT, 1, 1);\n        BonsaiNativeProfileAdd(2, 1);')
    replace_once(ops,'    ggml_metal_encoder_dispatch_threadgroups(enc, n_tg, 1, 1, 32*sg_per_tg, 1, 1);',
                 '    ggml_metal_encoder_dispatch_threadgroups(enc, n_tg, 1, 1, 32*sg_per_tg, 1, 1);\n    BonsaiNativeProfileAdd(2, 1);')
    replace_once(dev,'    [encoder->obj dispatchThreadgroups:MTLSizeMake(tg0, tg1, tg2) threadsPerThreadgroup:MTLSizeMake(tptg0, tptg1, tptg2)];',
                 '    [encoder->obj dispatchThreadgroups:MTLSizeMake(tg0, tg1, tg2) threadsPerThreadgroup:MTLSizeMake(tptg0, tptg1, tptg2)];\n    BonsaiNativeProfileAdd(3, 1);')
    run_diff_check(root)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);apply(p.parse_args().root)
