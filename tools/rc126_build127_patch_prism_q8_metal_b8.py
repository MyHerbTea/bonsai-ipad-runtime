#!/usr/bin/env python3
"""Build127 opt-in Metal PTQ1 B8 path; apply after the Build126 KV observation patch."""
from pathlib import Path
import argparse

from rc126_build113_patch_prism_ptq1_tensorops import BASE_SHA, run_git, run_diff_check

FLAG_CPU_SDOT = 64
FLAG_METAL_B8 = 256
FLAG_CANDIDATE = FLAG_CPU_SDOT | FLAG_METAL_B8
MARKER = "BONSAI_Q8_METAL_B8_127"

GATE_HEADER = (Path(__file__).parent / "native/build127_q8_metal_b8.h").read_text(encoding="utf-8")

def render_gate_header():
    return GATE_HEADER

def once(source, old, new, label):
    count = source.count(old)
    if count != 1:
        raise ValueError(f"Build127 source drift for {label}: expected one anchor, found {count}")
    return source.replace(old, new, 1)

def patch_kernel_source(source):
    if MARKER in source:
        raise ValueError("Build127 Metal kernel already patched")
    anchor = 'template [[host_name("kernel_mul_mv_ext_ptq1_0_f32_r1_5")]] kernel mul_mv_ext_q4_f32_t kernel_mul_mv_ext_q4_f32_disp<5, block_ptq1_0, 128, dequantize_ptq1_0_t4>;'
    addition = anchor + '\n' + (
        'template [[host_name("kernel_mul_mv_ext_ptq1_0_f32_r1_8")]] '
        'kernel mul_mv_ext_q4_f32_t kernel_mul_mv_ext_q4_f32_disp'
        '<8, block_ptq1_0, 128, dequantize_ptq1_0_t4>; // ' + MARKER
    )
    return once(source, anchor, addition, "PTQ1 r1_5 template")

def patch_ops_source(source):
    if MARKER in source:
        raise ValueError("Build127 Metal ops already patched")
    source = once(source, '#include "ggml-metal-ops.h"',
        '#include "ggml-metal-ops.h"\n#include "build127_q8_metal_b8.h"', "gate header include")
    source = once(source,
        'if (flags != 32 && flags != 64 && flags != 128 && (flags < -1 || flags > 31 || (flags >= 0 && (flags & 24) == 24))) return 0;',
        'if (flags != 32 && flags != 64 && flags != 128 && flags != 320 && (flags < -1 || flags > 31 || (flags >= 0 && (flags & 24) == 24))) return 0;',
        "candidate flag whitelist")
    source = once(source, 'BonsaiNativeCPUConfigure(flags);',
        'BonsaiNativeCPUConfigure(bonsai_q8_metal_b8_cpu_flags(flags));', "CPU flag mask")
    source = once(source, 'static std::atomic<uint64_t> bonsai_benchmark_counts[10]{};',
        'static std::atomic<uint64_t> bonsai_benchmark_counts[14]{};', "counter storage")
    source = once(source, 'if (index >= 0 && index < 10) bonsai_benchmark_counts[index].fetch_add(1, std::memory_order_release);',
        'if (index >= 0 && index < 14) bonsai_benchmark_counts[index].fetch_add(1, std::memory_order_release);', "counter increment range")
    source = once(source, 'default: return index >= 0 && index < 10 ? bonsai_benchmark_counts[index].load(std::memory_order_acquire) : 0;',
        'default: return index >= 0 && index < 14 ? bonsai_benchmark_counts[index].load(std::memory_order_acquire) : 0;', "counter read range")

    dispatch_anchor = """        };

        auto pipeline = ggml_metal_library_get_pipeline_mul_mv_ext(lib, op, nsg, nxpsg, r1ptg);"""
    dispatch_replacement = """        };

        const int32_t bonsai_flags = bonsai_benchmark_flags.load(std::memory_order_acquire);
        const bool bonsai_q8_metal_b8 = bonsai_q8_metal_b8_eligible(
            bonsai_flags,
            props_dev->device_id >= GGML_METAL_DEVICE_M5 &&
                (BonsaiNativeBenchmarkCapabilities() & 256u) != 0,
            op->src[0]->type == GGML_TYPE_PTQ1_0,
            op->src[1]->type == GGML_TYPE_F32,
            op->type == GGML_TYPE_F32,
            !ggml_is_transposed(op->src[0]) && !ggml_is_transposed(op->src[1]) &&
                ggml_is_contiguous(op->src[0]) && ggml_is_contiguous(op->src[1]) &&
                ggml_is_contiguous(op),
            ne00 > 0 && ne00 % 128 == 0 && ne12 == 1 && ne13 == 1,
            ne11);
        if (bonsai_q8_metal_b8) {
            r1ptg = 8;
            BonsaiNativeBenchmarkIncrement(10); // eligible and route requested
        }

        auto pipeline = ggml_metal_library_get_pipeline_mul_mv_ext(lib, op, nsg, nxpsg, r1ptg);
        bool bonsai_q8_metal_b8_dispatch = false;
        if (bonsai_q8_metal_b8 && !pipeline.pipeline) {
            BonsaiNativeBenchmarkIncrement(13); // attempted candidate pipeline failed
            r1ptg = 4;
            pipeline = ggml_metal_library_get_pipeline_mul_mv_ext(lib, op, nsg, nxpsg, r1ptg);
        } else if (bonsai_q8_metal_b8) {
            BonsaiNativeBenchmarkIncrement(11); // candidate pipeline is available
            bonsai_q8_metal_b8_dispatch = true;
        }"""
    source = once(source, dispatch_anchor, dispatch_replacement, "B8 dispatch selection")
    dispatch = 'ggml_metal_encoder_dispatch_threadgroups(enc, ((ne01 + r0ptg - 1)/r0ptg), ((ne11 + r1ptg - 1)/r1ptg), ne12*ne13, 32, nsg, 1);'
    source = once(source, dispatch,
        dispatch + '\n        if (bonsai_q8_metal_b8_dispatch && pipeline.pipeline) BonsaiNativeBenchmarkIncrement(12);',
        "B8 dispatch evidence")
    return source + '\n// ' + MARKER + ': fixed-Q8 opt-in B8 route; generic dispatch is retained.\n'

def patch_device_source(source):
    anchor = 'BonsaiNativeBenchmarkPublishCapabilities(6u | ((dev->props.has_tensor_benchmark && BonsaiNativeBenchmarkTensorSourceAvailable()) ? 1u : 0u));'
    return once(source, anchor,
        'BonsaiNativeBenchmarkPublishCapabilities(6u | ((dev->props.has_tensor_benchmark && BonsaiNativeBenchmarkTensorSourceAvailable()) ? 1u : 0u) | 256u);',
        "M5 B8 capability")

def apply(root):
    root = Path(root).resolve()
    if run_git(root, "rev-parse", "HEAD") != BASE_SHA:
        raise SystemExit("wrong pinned Prism revision")
    metal = root / "ggml/src/ggml-metal"
    kernel = metal / "kernels/mul_mv.metal"
    ops = metal / "ggml-metal-ops.cpp"
    device = metal / "ggml-metal-device.m"
    kernel.write_text(patch_kernel_source(kernel.read_text(encoding="utf-8")), encoding="utf-8")
    ops.write_text(patch_ops_source(ops.read_text(encoding="utf-8")), encoding="utf-8")
    device.write_text(patch_device_source(device.read_text(encoding="utf-8")), encoding="utf-8")
    (metal / "build127_q8_metal_b8.h").write_text(GATE_HEADER, encoding="utf-8")
    run_diff_check(root)
    print("Build127 fixed-Q8 PTQ1 Metal B8 source patch: PASS")
    print("Candidate route: M5 + PTQ1_0/F32 + contiguous compatible B8 + explicit flags 320")
    print("Q8 KV tensors are not modified; pipeline failure retries inherited r1ptg=4")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("prism_dir", type=Path)
    apply(parser.parse_args().prism_dir)