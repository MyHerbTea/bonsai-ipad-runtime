#!/usr/bin/env python3
"""Pinned Prism PTQ1 benchmark ABI, isolated Tensor source and five-row fused matvec.

Run after build83..89 and both build113 patches. No production policy is changed
at runtime: has_tensor remains latched, while this benchmark owns a separate mask.
"""
from pathlib import Path
import argparse
from rc126_build113_patch_prism_ptq1_tensorops import BASE_SHA, run_git, replace_once, run_diff_check

MARKER = 'BONSAI_PTQ1_BENCHMARK_114'

DECLARATIONS = '''
// BONSAI_PTQ1_BENCHMARK_114: C linkage across C++ and Objective-C Metal host.
__attribute__((visibility("default"))) int32_t BonsaiNativeBenchmarkConfigure(int32_t flags);
__attribute__((visibility("default"))) uint32_t BonsaiNativeBenchmarkCapabilities(void);
__attribute__((visibility("default"))) uint64_t BonsaiNativeBenchmarkCounter(int index);
__attribute__((visibility("default"))) void BonsaiNativeBenchmarkBeginRequest(void);
__attribute__((visibility("default"))) int64_t BonsaiNativeBenchmarkObservation(int index);
void BonsaiNativeBenchmarkObserve(int arm, const struct ggml_tensor * op);
bool BonsaiNativeBenchmarkTensorEnabled(bool production);
bool BonsaiNativeBenchmarkFusedEnabled(const struct ggml_tensor * op);
void BonsaiNativeBenchmarkPublishCapabilities(uint32_t flags);
void BonsaiNativeBenchmarkIncrement(int index);
void BonsaiNativeBenchmarkFusedFailed(void);
void BonsaiNativeBenchmarkTensorFailed(void);
bool BonsaiNativeBenchmarkTensorSourceAvailable(void);
'''

CONTROL = r'''
// BONSAI_PTQ1_BENCHMARK_114. Configuration requires a quiescent context; the app
// owns the exclusive session and synchronizes/frees its context before calling.
static std::atomic<int32_t> bonsai_benchmark_flags{-1};
static std::atomic<uint32_t> bonsai_benchmark_caps{0};
static std::atomic_bool bonsai_benchmark_tensor_source{true};
static std::atomic<uint64_t> bonsai_benchmark_counts[10]{};
// Bounded first eligible operation per arm per request, queried only after sync.
static std::atomic<int64_t> bonsai_benchmark_observed[20]{};
static std::atomic_flag bonsai_benchmark_observed_once[2] = {ATOMIC_FLAG_INIT, ATOMIC_FLAG_INIT};
extern "C" __attribute__((visibility("default")))
void BonsaiNativeBenchmarkBeginRequest(void) {
    for (auto & value : bonsai_benchmark_observed) value.store(0, std::memory_order_relaxed);
    for (auto & once : bonsai_benchmark_observed_once) once.clear(std::memory_order_release);
}
extern "C" __attribute__((visibility("default")))
int64_t BonsaiNativeBenchmarkObservation(int index) {
    return index >= 0 && index < 20 ? bonsai_benchmark_observed[index].load(std::memory_order_acquire) : 0;
}
extern "C" void BonsaiNativeBenchmarkObserve(int arm, const ggml_tensor * op) {
    if (arm < 0 || arm > 1 || bonsai_benchmark_observed_once[arm].test_and_set(std::memory_order_acq_rel)) return;
    const int64_t values[10] = {op->src[0]->ne[0], op->src[1]->ne[1], op->src[0]->ne[1],
        (int64_t)op->src[0]->nb[0], (int64_t)op->src[0]->nb[1],
        (int64_t)op->src[1]->nb[0], (int64_t)op->src[1]->nb[1],
        (int64_t)op->nb[0], (int64_t)op->nb[1], 1};
    for (int i = 0; i < 10; ++i) bonsai_benchmark_observed[arm*10+i].store(values[i], std::memory_order_release);
}


extern "C" __attribute__((visibility("default")))
uint32_t BonsaiNativeBenchmarkCapabilities(void) {
    return bonsai_benchmark_caps.load(std::memory_order_acquire);
}
extern "C" __attribute__((visibility("default")))
int32_t BonsaiNativeBenchmarkConfigure(int32_t flags) {
    if (flags < -1 || flags > 7) return 0;
    if (flags >= 0 && ((uint32_t) flags & ~BonsaiNativeBenchmarkCapabilities())) return 0;
    // Count submitted versus terminal buffers, never infer GPU completion from
    // dispatch enqueue. The session must already have synchronized the backend.
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(100);
    while (bonsai_benchmark_counts[6].load(std::memory_order_acquire) !=
           bonsai_benchmark_counts[7].load(std::memory_order_acquire) +
           bonsai_benchmark_counts[8].load(std::memory_order_acquire)) {
        if (std::chrono::steady_clock::now() >= deadline) return 0;
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    bonsai_benchmark_flags.store(flags, std::memory_order_release);
    return 1;
}
extern "C" void BonsaiNativeBenchmarkIncrement(int index) {
    if (index >= 0 && index < 10) bonsai_benchmark_counts[index].fetch_add(1, std::memory_order_release);
}
extern "C" void BonsaiNativeBenchmarkPublishCapabilities(uint32_t flags) {
    bonsai_benchmark_caps.store(flags, std::memory_order_release);
}
extern "C" void BonsaiNativeBenchmarkTensorFailed(void) {
    bonsai_benchmark_tensor_source.store(false, std::memory_order_release);
    bonsai_benchmark_caps.fetch_and(~1u, std::memory_order_release);
}
extern "C" bool BonsaiNativeBenchmarkTensorSourceAvailable(void) {
    return bonsai_benchmark_tensor_source.load(std::memory_order_acquire);
}
extern "C" void BonsaiNativeBenchmarkFusedFailed(void) {
    bonsai_benchmark_caps.fetch_and(~2u, std::memory_order_release);
    BonsaiNativeBenchmarkIncrement(9);
}
extern "C" bool BonsaiNativeBenchmarkTensorEnabled(bool production) {
    const int32_t flags = bonsai_benchmark_flags.load(std::memory_order_acquire);
    return flags < 0 ? production : (flags & 1) != 0;
}
extern "C" bool BonsaiNativeBenchmarkFusedEnabled(const ggml_tensor * op) {
    return (bonsai_benchmark_flags.load(std::memory_order_acquire) & 2) != 0 &&
        bonsai_benchmark_flags.load(std::memory_order_relaxed) >= 0 &&
        (BonsaiNativeBenchmarkCapabilities() & 2) &&
        op->src[0]->type == GGML_TYPE_PTQ1_0 && op->src[1]->type == GGML_TYPE_F32 &&
        op->type == GGML_TYPE_F32 && !ggml_is_transposed(op->src[0]) &&
        !ggml_is_transposed(op->src[1]) && op->src[1]->ne[1] == 1 &&
        op->src[0]->ne[0] % 128 == 0 && op->src[0]->ne[1] >= 5 &&
        op->src[1]->nb[0] == sizeof(float) && op->nb[0] == sizeof(float);
}
extern "C" __attribute__((visibility("default")))
uint64_t BonsaiNativeBenchmarkCounter(int index) {
    switch (index) {
        case 0: return bonsai_ptq1_route_selected_count.load(std::memory_order_relaxed);
        case 1: return bonsai_ptq1_pipeline_ready_count.load(std::memory_order_relaxed);
        case 2: return bonsai_ptq1_dispatch_enqueued_count.load(std::memory_order_relaxed);
        case 9: return bonsai_benchmark_counts[9].load(std::memory_order_relaxed) +
                       bonsai_ptq1_fallback_count.load(std::memory_order_relaxed);
        default: return index >= 0 && index < 10 ? bonsai_benchmark_counts[index].load(std::memory_order_acquire) : 0;
    }
}
'''

COMPLETION = '''
// Completion callbacks record terminal GPU status. Global atomics outlive contexts;
// callbacks capture no freed context or model. Submitted counts only actual commits.
static void bonsai_benchmark_commit(id<MTLCommandBuffer> command) {
    BonsaiNativeBenchmarkIncrement(6);
    [command addCompletedHandler:^(id<MTLCommandBuffer> completed) {
        if (completed.status == MTLCommandBufferStatusCompleted) {
            BonsaiNativeBenchmarkIncrement(7);
        } else {
            BonsaiNativeBenchmarkIncrement(8);
        }
    }];
    [command commit];
}
'''


def apply(root):
    if run_git(root, 'rev-parse', 'HEAD') != BASE_SHA:
        raise SystemExit('wrong Prism base; expected ' + BASE_SHA)
    metal = root / 'ggml/src/ggml-metal'
    ops = metal / 'ggml-metal-ops.cpp'
    h = metal / 'ggml-metal-device.h'
    dev = metal / 'ggml-metal-device.m'
    cpp = metal / 'ggml-metal-device.cpp'
    mv = metal / 'kernels/mul_mv.metal'
    mm = metal / 'kernels/mul_mm.metal'
    if MARKER in ops.read_text(encoding='utf-8'):
        raise SystemExit('benchmark patch already applied')

    replace_once(ops, "#include <stdint.h>\n", "#include <stdint.h>\n#include <chrono>\n#include <thread>\n")
    replace_once(h, 'bool ggml_metal_ptq1_multicol_enabled', DECLARATIONS + '\nbool ggml_metal_ptq1_multicol_enabled')
    replace_once(h, '    bool has_tensor;\n', '    bool has_tensor;\n    bool has_tensor_benchmark; // immutable source capability, independent of launch disable\n')
    replace_once(ops, 'static inline void bonsai_m5_ptq1_tensor_trace', CONTROL + '\nstatic inline void bonsai_m5_ptq1_tensor_trace')
    replace_once(ops, '        props_dev->has_tensor &&\n        props_dev->has_simdgroup_mm &&\n        props_dev->device_id >= GGML_METAL_DEVICE_M5 &&\n        op->src[0]->type == GGML_TYPE_PTQ1_0',
                 '        props_dev->has_tensor_benchmark &&\n        BonsaiNativeBenchmarkTensorEnabled(props_dev->has_tensor && !ptq1_tensorops_disabled) &&\n        props_dev->has_simdgroup_mm &&\n        props_dev->device_id >= GGML_METAL_DEVICE_M5 &&\n        op->src[0]->type == GGML_TYPE_PTQ1_0')
    # The legacy env flag is production policy only. Benchmark flags supersede it.
    replace_once(ops, '        !ptq1_tensorops_disabled &&\n', '')
    replace_once(ops, '        bonsai_ptq1_route_selected_count.fetch_add(1, std::memory_order_relaxed);',
                 '        bonsai_ptq1_route_selected_count.fetch_add(1, std::memory_order_relaxed);\n        BonsaiNativeBenchmarkObserve(0, op);')
    replace_once(ops, '            ptq1_tensorops_pipeline_failed.store(true, std::memory_order_relaxed);',
                 '            ptq1_tensorops_pipeline_failed.store(true, std::memory_order_relaxed);\n            BonsaiNativeBenchmarkTensorFailed();')
    # Build113 returned zero on failure, which is not the inherited operation path.
    replace_once(ops, '            return 0;\n        }\n        bonsai_ptq1_pipeline_ready_count',
                 '            goto bonsai_ptq1_inherited;\n        }\n        bonsai_ptq1_pipeline_ready_count')
    replace_once(ops, '    if (ggml_metal_op_mul_mat_q1_0_pc_supported(op)) {\n',
                 'bonsai_ptq1_inherited:\n    if (ggml_metal_op_mul_mat_q1_0_pc_supported(op)) {\n')

    replace_once(cpp, '                nr0 = N_R0_PTQ1_0;\n                if (ggml_metal_ptq1_multicol_enabled(op))',
                 '                nr0 = N_R0_PTQ1_0;\n                if (BonsaiNativeBenchmarkFusedEnabled(op)) { nr0 = 5; suffix = "_bonsai_r5"; }\n                if (ggml_metal_ptq1_multicol_enabled(op))')
    # This pipeline getter also serves ordinary mv ops. Re-enter once with the
    # capability cleared after compilation failure to get the original r4 kernel.
    replace_once(cpp, '    res.nr0  = nr0;\n    res.nr1  = nr1;\n    res.nsg  = nsg;\n    res.smem = smem;\n\n    return res;\n}\n\nggml_metal_pipeline_with_params ggml_metal_library_get_pipeline_mul_mm_id_map0',
                 '    if (!res.pipeline && tsrc0 == GGML_TYPE_PTQ1_0 && nr0 == 5) {\n        BonsaiNativeBenchmarkFusedFailed();\n        return ggml_metal_library_get_pipeline_mul_mv(lib, op);\n    }\n    res.nr0  = nr0;\n    res.nr1  = nr1;\n    res.nsg  = nsg;\n    res.smem = smem;\n\n    return res;\n}\n\nggml_metal_pipeline_with_params ggml_metal_library_get_pipeline_mul_mm_id_map0')
    replace_once(ops, '        auto pipeline = ggml_metal_library_get_pipeline_mul_mv(lib, op);\n',
                 '        if (BonsaiNativeBenchmarkFusedEnabled(op)) { BonsaiNativeBenchmarkIncrement(3); BonsaiNativeBenchmarkObserve(1, op); }\n        auto pipeline = ggml_metal_library_get_pipeline_mul_mv(lib, op);\n        const bool bonsai_fused_dispatched = op->src[0]->type == GGML_TYPE_PTQ1_0 && pipeline.nr0 == 5;\n        if (bonsai_fused_dispatched && pipeline.pipeline) BonsaiNativeBenchmarkIncrement(4);\n')
    replace_once(ops, '            ggml_metal_encoder_dispatch_threadgroups(enc, ((ne01 + nr0*nsg - 1)/(nr0*nsg)), ((ne11 + nr1 - 1)/nr1), ne12*ne13, 32, nsg, 1);\n',
                 '            ggml_metal_encoder_dispatch_threadgroups(enc, ((ne01 + nr0*nsg - 1)/(nr0*nsg)), ((ne11 + nr1 - 1)/nr1), ne12*ne13, 32, nsg, 1);\n            if (bonsai_fused_dispatched) BonsaiNativeBenchmarkIncrement(5);\n')
    replace_once(mv, '            sumf[row] += ptq1_0_dot_reg(ax[row] + ib, yl, sumy, it);',
                 '            if (nr0 != 5 || first_row + row < args.ne01) {\n                sumf[row] += ptq1_0_dot_reg(ax[row] + ib, yl, sumy, it);\n            }')
    # Separate host name/cache entry: baseline remains the exact r4 instantiation.
    source = mv.read_text(encoding='utf-8')
    start = source.index('[[host_name("kernel_mul_mv_ptq1_0_f32")]]')
    end = source.index('\n}', start) + 2
    variant = source[start:end].replace('kernel_mul_mv_ptq1_0_f32\"', 'kernel_mul_mv_ptq1_0_f32_bonsai_r5\"').replace('void kernel_mul_mv_ptq1_0_f32(', 'void kernel_mul_mv_ptq1_0_f32_bonsai_r5(').replace('<N_R0_PTQ1_0,', '<5,')
    mv.write_text(source[:end] + '\n\n// ' + MARKER + ': 5 rows share register activation coefficients.\n' + variant + source[end:], encoding='utf-8')

    # Compile the existing PTQ1 Tensor code without changing the generic Tensor
    # kernels or their tile sizes when the production launch disables TensorOps.
    source = mm.read_text(encoding='utf-8')
    start = source.index('// BONSAI_M5_PTQ1_TENSOROPS_01')
    start = source.rfind('#ifdef GGML_METAL_HAS_TENSOR', 0, start)
    mm.write_text(source[:start] + source[start:].replace('GGML_METAL_HAS_TENSOR', 'GGML_METAL_HAS_BONSAI_PTQ1_TENSOR'), encoding='utf-8')
    replace_once(metal / 'kernels/common.h', '#ifdef GGML_METAL_HAS_TENSOR\n',
                 '#if defined(GGML_METAL_HAS_TENSOR) || defined(GGML_METAL_HAS_BONSAI_PTQ1_TENSOR)\n')
    # Probe Tensor API once independent of the environment launch policy; freeze
    # that capability before applying policy. Never rewrite registry props later.
    disable = '            if (getenv("GGML_METAL_TENSOR_DISABLE") != NULL) {\n                dev->props.has_tensor = false;\n            }\n'
    replace_once(dev, disable, '')
    replace_once(dev, '            // try to compile a dummy kernel to determine if the tensor API is supported for bfloat',
                 '            dev->props.has_tensor_benchmark = dev->props.has_tensor;\n' + disable + '\n            // try to compile a dummy kernel to determine if the tensor API is supported for bfloat')
    replace_once(dev, '    if (ggml_metal_device_get_props(dev)->has_tensor) {\n        [prep setObject:@"1" forKey:@"GGML_METAL_HAS_TENSOR"];\n    }',
                 '    if (ggml_metal_device_get_props(dev)->has_tensor) {\n        [prep setObject:@"1" forKey:@"GGML_METAL_HAS_TENSOR"];\n    }\n    if (ggml_metal_device_get_props(dev)->has_tensor_benchmark) {\n        [prep setObject:@"1" forKey:@"GGML_METAL_HAS_BONSAI_PTQ1_TENSOR"];\n    }')
    source = dev.read_text(encoding='utf-8')
    for obj in ('res->dev', 'dev'):
        old = f'ggml_metal_compile_options_set_lang(options, ggml_metal_device_get_props({obj})->has_tensor);'
        new = f'ggml_metal_compile_options_set_lang(options, ggml_metal_device_get_props({obj})->has_tensor || ggml_metal_device_get_props({obj})->has_tensor_benchmark);'
        source = source.replace(old, new)
    dev.write_text(source, encoding='utf-8')
    replace_once(dev, '            if (dev->props.use_residency_sets) {\n',
                 '            // Publish only after the real source library has compiled.\n            if (dev->library && dev->props.device_id >= GGML_METAL_DEVICE_M5) {\n                BonsaiNativeBenchmarkPublishCapabilities(6u | ((dev->props.has_tensor_benchmark && BonsaiNativeBenchmarkTensorSourceAvailable()) ? 1u : 0u));\n            }\n\n            if (dev->props.use_residency_sets) {\n')
    # Retry only the failed source without benchmark-only Tensor code. This
    # preserves baseline model availability if the real candidate source fails.
    replace_once(dev, '                lib = [device newLibraryWithSource:src options:options error:&error];',
                 '                lib = [device newLibraryWithSource:src options:options error:&error];\n'
                 '                if (!lib && [prep objectForKey:@"GGML_METAL_HAS_BONSAI_PTQ1_TENSOR"]) {\n'
                 '                    BonsaiNativeBenchmarkTensorFailed();\n'
                 '                    NSMutableDictionary * fallback = [prep mutableCopy];\n'
                 '                    [fallback removeObjectForKey:@"GGML_METAL_HAS_BONSAI_PTQ1_TENSOR"];\n'
                 '                    options.preprocessorMacros = fallback;\n'
                 '                    [fallback release];\n'
                 '                    error = nil;\n'
                 '                    lib = [device newLibraryWithSource:src options:options error:&error];\n'
                 '                }')
    context = metal / 'ggml-metal-context.m'
    replace_once(context, '// max number of MTLCommandBuffer', COMPLETION + '\n// max number of MTLCommandBuffer')
    source = context.read_text(encoding='utf-8')
    source = source.replace('[cmd_buf commit];', 'bonsai_benchmark_commit(cmd_buf);')
    source = source.replace('[next_buffer commit];', 'bonsai_benchmark_commit(next_buffer);')
    context.write_text(source, encoding='utf-8')
    run_diff_check(root)
    print(MARKER + ': PASS (source application only; GPU validation pending)')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('prism_dir', type=Path)
    apply(parser.parse_args().prism_dir.resolve())
