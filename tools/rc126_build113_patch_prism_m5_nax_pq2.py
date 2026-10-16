#!/usr/bin/env python3
"""Apply the experimental Bonsai M5-NAX-PQ2-01 kernel to an exact Prism checkout."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

BASE_SHA = "adfffbe41b2cabcd51fff326ab045662265062bb"
MARKER = "BONSAI_M5_NAX_PQ2_01"

KERNEL = r"""
#ifdef GGML_METAL_HAS_TENSOR

// BONSAI_M5_NAX_PQ2_01
// Register-resident custom dequant path:
// PQ2_0 -> half fragments -> cooperative TensorOps input.
// No threadgroup staging for the quantized weight tile.
//
// Tile: 64 x 128 output, 2 x 4 simdgroups, 32 x 32 per simdgroup.
// K is consumed as 16-wide TensorOps fragments, with a 128-wide
// synchronization/cache working set. Host routing limits this candidate
// to K % 128 == 0 large-prefill shapes.

static inline short2 bonsai_m5_nax_pq2_coord(ushort lane) {
    const short qid = lane >> 2;
    const short fm  = (qid & 4) | ((lane >> 1) & 3);
    const short fn  = ((qid & 2) | (lane & 1))*4;
    return short2(fn, fm);
}

static inline half4 bonsai_m5_nax_pq2_decode4(
        device const block_pq2_0 * row_blocks,
        int kpos) {
    const int block_index = kpos / QK_PQ2_0;
    const int in_block    = kpos - block_index*QK_PQ2_0;
    const block_pq2_0 * block = row_blocks + block_index;
    const uchar q = block->qs[in_block >> 2];
    const float d = block->d;

    return half4(
        half(((int)((q >> 0) & 3) - 1) * d),
        half(((int)((q >> 2) & 3) - 1) * d),
        half(((int)((q >> 4) & 3) - 1) * d),
        half(((int)((q >> 6) & 3) - 1) * d)
    );
}

static inline void bonsai_m5_nax_pq2_mma(
        thread vec<float, 8> & c0,
        thread vec<float, 8> & c1,
        thread const vec<half, 8> & a,
        thread const vec<half, 8> & b0,
        thread const vec<half, 8> & b1) {
    constexpr auto desc = mpp::tensor_ops::matmul2d_descriptor(
        16, 32, 16, false, true, true,
        mpp::tensor_ops::matmul2d_descriptor::mode::multiply_accumulate);

    mpp::tensor_ops::matmul2d<desc, execution_simdgroup> op;

    auto ca = op.template get_left_input_cooperative_tensor<half, half, float>();
    auto cb = op.template get_right_input_cooperative_tensor<half, half, float>();
    auto cc = op.template get_destination_cooperative_tensor<
        remove_addrspace_t<decltype(ca)>,
        remove_addrspace_t<decltype(cb)>,
        float>();

    FOR_UNROLL (short i = 0; i < 8; ++i) {
        ca[i]     = a[i];
        cb[i]     = b0[i];
        cb[8 + i] = b1[i];
        cc[i]     = c0[i];
        cc[8 + i] = c1[i];
    }

    op.run(ca, cb, cc);

    FOR_UNROLL (short i = 0; i < 8; ++i) {
        c0[i] = cc[i];
        c1[i] = cc[8 + i];
    }
}

[[kernel, max_total_threads_per_threadgroup(256)]]
void kernel_mul_mm_nax_pq2_0_f32(
        constant ggml_metal_kargs_mul_mm & args,
        device const char * src0,
        device const char * src1,
        device       char * dst,
        uint3 tgpig [[threadgroup_position_in_grid]],
        ushort tiisg [[thread_index_in_simdgroup]],
        ushort sgitg [[simdgroup_index_in_threadgroup]]) {
    constexpr short BM = 64;
    constexpr short BN = 128;
    constexpr short WM = 2;
    constexpr short WN = 4;
    constexpr short SM = BM/WM;
    constexpr short SN = BN/WN;
    constexpr short TM = SM/16;
    constexpr short TN = SN/16;

    const int K = args.ne00;
    const int M = args.ne1;
    const int N = args.ne0;

    const int tile_m = tgpig.x;
    const int tile_n = tgpig.y;

    if (tile_m*BM >= M || tile_n*BN >= N) {
        return;
    }

    const int m0 = tile_m*BM + SM*(sgitg/WN);
    const int n0 = tile_n*BN + SN*(sgitg%WN);
    const short2 sc = bonsai_m5_nax_pq2_coord(tiisg);

    device const float * pa[TM][2];
    device const block_pq2_0 * pb[TN][2];

    FOR_UNROLL (short mm = 0; mm < TM; ++mm) {
        FOR_UNROLL (short i = 0; i < 2; ++i) {
            const int r = min(m0 + mm*16 + sc.y + i*8, M - 1);
            pa[mm][i] = (device const float *)(src1 + args.nb11*(uint64_t)r);
        }
    }

    FOR_UNROLL (short nn = 0; nn < TN; ++nn) {
        FOR_UNROLL (short i = 0; i < 2; ++i) {
            const int r = min(n0 + nn*16 + sc.y + i*8, N - 1);
            pb[nn][i] = (device const block_pq2_0 *)(
                src0 + args.nb01*(uint64_t)r);
        }
    }

    vec<float, 8> c[TM][TN];
    FOR_UNROLL (short mm = 0; mm < TM; ++mm) {
        FOR_UNROLL (short nn = 0; nn < TN; ++nn) {
            c[mm][nn] = 0.0f;
        }
    }

    for (int k0 = 0; k0 < K; k0 += 128) {
        threadgroup_barrier(mem_flags::mem_none);

        for (int k = k0; k < k0 + 128; k += 16) {
            vec<half, 8> a[TM];
            vec<half, 8> b[TN];

            FOR_UNROLL (short mm = 0; mm < TM; ++mm) {
                const int kp = k + sc.x;
                const float4 va0 = *((device const float4 *)(pa[mm][0] + kp));
                const float4 va1 = *((device const float4 *)(pa[mm][1] + kp));

                a[mm][0] = half(va0[0]);
                a[mm][1] = half(va0[1]);
                a[mm][2] = half(va0[2]);
                a[mm][3] = half(va0[3]);
                a[mm][4] = half(va1[0]);
                a[mm][5] = half(va1[1]);
                a[mm][6] = half(va1[2]);
                a[mm][7] = half(va1[3]);
            }

            FOR_UNROLL (short nn = 0; nn < TN; ++nn) {
                const int kp = k + sc.x;
                const half4 vb0 = bonsai_m5_nax_pq2_decode4(pb[nn][0], kp);
                const half4 vb1 = bonsai_m5_nax_pq2_decode4(pb[nn][1], kp);

                b[nn][0] = vb0[0];
                b[nn][1] = vb0[1];
                b[nn][2] = vb0[2];
                b[nn][3] = vb0[3];
                b[nn][4] = vb1[0];
                b[nn][5] = vb1[1];
                b[nn][6] = vb1[2];
                b[nn][7] = vb1[3];
            }

            FOR_UNROLL (short mm = 0; mm < TM; ++mm) {
                FOR_UNROLL (short nn = 0; nn < TN; nn += 2) {
                    bonsai_m5_nax_pq2_mma(
                        c[mm][nn], c[mm][nn + 1],
                        a[mm], b[nn], b[nn + 1]);
                }
            }
        }
    }

    FOR_UNROLL (short mm = 0; mm < TM; ++mm) {
        FOR_UNROLL (short i = 0; i < 2; ++i) {
            const int r = m0 + mm*16 + sc.y + i*8;
            if (r >= M) {
                continue;
            }

            device float * d = (device float *)dst + (uint64_t)r*args.ne0;

            FOR_UNROLL (short nn = 0; nn < TN; ++nn) {
                const int col = n0 + nn*16 + sc.x;
                const float4 v = float4(
                    c[mm][nn][i*4 + 0],
                    c[mm][nn][i*4 + 1],
                    c[mm][nn][i*4 + 2],
                    c[mm][nn][i*4 + 3]);

                if (col + 3 < N) {
                    *((device float4 *)(d + col)) = v;
                } else {
                    FOR_UNROLL (short j = 0; j < 4; ++j) {
                        if (col + j < N) {
                            d[col + j] = v[j];
                        }
                    }
                }
            }
        }
    }
}

typedef decltype(kernel_mul_mm_nax_pq2_0_f32) bonsai_m5_nax_pq2_t;
template [[host_name("kernel_mul_mm_nax_pq2_0_f32")]]
kernel bonsai_m5_nax_pq2_t kernel_mul_mm_nax_pq2_0_f32;

#endif // GGML_METAL_HAS_TENSOR
"""

def run_git(path: Path, *args: str) -> str:
    p = subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return p.stdout.strip()

def replace_once(path: Path, old: str, new: str) -> None:
    source = path.read_text(encoding="utf-8")
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one anchor, found {count}")
    path.write_text(source.replace(old, new), encoding="utf-8")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prism_dir", type=Path)
    args = parser.parse_args()

    root = args.prism_dir.resolve()
    if not (root / ".git").exists():
        raise SystemExit(f"not a git checkout: {root}")

    head = run_git(root, "rev-parse", "HEAD")
    if head != BASE_SHA:
        raise SystemExit(f"wrong Prism base: {head}; expected {BASE_SHA}")

    impl_h = root / "ggml/src/ggml-metal/ggml-metal-impl.h"
    device_h = root / "ggml/src/ggml-metal/ggml-metal-device.h"
    device_cpp = root / "ggml/src/ggml-metal/ggml-metal-device.cpp"
    ops_cpp = root / "ggml/src/ggml-metal/ggml-metal-ops.cpp"
    mm_metal = root / "ggml/src/ggml-metal/kernels/mul_mm.metal"

    if MARKER in mm_metal.read_text(encoding="utf-8"):
        raise SystemExit("PQ2 NAX patch already applied")

    replace_once(
        impl_h,
        "#define N_MM_SIMD_GROUP_Y 2\n",
        "#define N_MM_SIMD_GROUP_Y 2\n"
        "// BONSAI_M5_NAX_PQ2_01 experimental register-resident PQ2 matmul.\n"
        "#define BONSAI_M5_NAX_PQ2_BM 64\n"
        "#define BONSAI_M5_NAX_PQ2_BN 128\n"
        "#define BONSAI_M5_NAX_PQ2_NSG 8\n",
    )

    replace_once(
        device_h,
        "struct ggml_metal_pipeline_with_params ggml_metal_library_get_pipeline_mul_mm            (ggml_metal_library_t lib, const struct ggml_tensor * op);\n",
        "struct ggml_metal_pipeline_with_params ggml_metal_library_get_pipeline_mul_mm            (ggml_metal_library_t lib, const struct ggml_tensor * op);\n"
        "struct ggml_metal_pipeline_with_params ggml_metal_library_get_pipeline_mul_mm_nax_pq2(ggml_metal_library_t lib);\n",
    )

    getter = """
struct ggml_metal_pipeline_with_params ggml_metal_library_get_pipeline_mul_mm_nax_pq2(ggml_metal_library_t lib) {
    const char * name = "kernel_mul_mm_nax_pq2_0_f32";

    ggml_metal_pipeline_with_params res = ggml_metal_library_get_pipeline(lib, name);
    if (!res.pipeline) {
        res = ggml_metal_library_compile_pipeline(lib, name, name, nullptr);
    }

    res.nr0 = BONSAI_M5_NAX_PQ2_BN;
    res.nr1 = BONSAI_M5_NAX_PQ2_BM;
    res.nsg = BONSAI_M5_NAX_PQ2_NSG;
    res.smem = 0;

    return res;
}

"""
    replace_once(
        device_cpp,
        "ggml_metal_pipeline_with_params ggml_metal_library_get_pipeline_mul_mm(ggml_metal_library_t lib, const ggml_tensor * op) {\n",
        getter
        + "ggml_metal_pipeline_with_params ggml_metal_library_get_pipeline_mul_mm(ggml_metal_library_t lib, const ggml_tensor * op) {\n",
    )

    gate = """
    // BONSAI_M5_NAX_PQ2_01:
    // custom PQ2 dequant -> cooperative TensorOps NAX-style kernel.
    // All other types and shapes continue through the inherited Prism paths.
    static const bool pq2_nax_disabled = getenv("GGML_METAL_PQ2_NAX_DISABLE") != nullptr;
    const bool use_pq2_nax =
        !pq2_nax_disabled &&
        props_dev->has_tensor &&
        props_dev->has_simdgroup_mm &&
        props_dev->device_id >= GGML_METAL_DEVICE_M5 &&
        op->src[0]->type == GGML_TYPE_PQ2_0 &&
        op->src[1]->type == GGML_TYPE_F32 &&
        !ggml_is_transposed(op->src[0]) &&
        !ggml_is_transposed(op->src[1]) &&
        ne00 % 128 == 0 &&
        ne11 >= 64 &&
        ne01 >= 128 &&
        ne02 == 1 && ne03 == 1 &&
        ne12 == 1 && ne13 == 1 &&
        nb10 == sizeof(float) &&
        op->nb[0] == sizeof(float) &&
        op->nb[1] == op->ne[0]*sizeof(float) &&
        nb01 % ggml_type_size(GGML_TYPE_PQ2_0) == 0;

    if (use_pq2_nax) {
        // Emit only the first eligible dispatch per process, and only while the
        // app's durable 32K native trace is enabled. Avoid perturbing prefill.
        static std::atomic_flag bonsai_m5_nax_pq2_trace_once = ATOMIC_FLAG_INIT;
        const bool trace_this_dispatch =
            std::getenv("BONSAI_BUILD84_TRACE_PATH") != nullptr &&
            !bonsai_m5_nax_pq2_trace_once.test_and_set(std::memory_order_relaxed);
        if (trace_this_dispatch) {
            bonsai_build84_trace(
                "BUILD113_M5_NAX_PQ2_ROUTE_SELECTED K=%d M=%d N=%d",
                ne00, ne11, ne01);
        }

        const auto pipeline = ggml_metal_library_get_pipeline_mul_mm_nax_pq2(lib);
        if (trace_this_dispatch) {
            bonsai_build84_trace(
                "BUILD113_M5_NAX_PQ2_PIPELINE_READY ok=%d nr0=%d nr1=%d nsg=%d",
                pipeline.pipeline != nullptr, pipeline.nr0, pipeline.nr1, pipeline.nsg);
        }

        ggml_metal_kargs_mul_mm args = {
            /*.ne00 =*/ ne00,
            /*.ne02 =*/ ne02,
            /*.nb01 =*/ nb01,
            /*.nb02 =*/ nb02,
            /*.nb03 =*/ nb03,
            /*.ne12 =*/ ne12,
            /*.nb10 =*/ nb10,
            /*.nb11 =*/ nb11,
            /*.nb12 =*/ nb12,
            /*.nb13 =*/ nb13,
            /*.ne0  =*/ ne0,
            /*.ne1  =*/ ne1,
            /*.r2   =*/ r2,
            /*.r3   =*/ r3,
        };

        ggml_metal_encoder_set_pipeline(enc, pipeline);
        ggml_metal_encoder_set_bytes   (enc, &args, sizeof(args), 0);
        ggml_metal_encoder_set_buffer  (enc, ggml_metal_get_buffer_id(op->src[0]), 1);
        ggml_metal_encoder_set_buffer  (enc, ggml_metal_get_buffer_id(op->src[1]), 2);
        ggml_metal_encoder_set_buffer  (enc, ggml_metal_get_buffer_id(op),         3);
        ggml_metal_encoder_set_threadgroup_memory_size(enc, pipeline.smem, 0);

        ggml_metal_encoder_dispatch_threadgroups(
            enc,
            (ne11 + pipeline.nr1 - 1)/pipeline.nr1,
            (ne01 + pipeline.nr0 - 1)/pipeline.nr0,
            ne12*ne13,
            32, pipeline.nsg, 1);

        if (trace_this_dispatch) {
            bonsai_build84_trace(
                "BUILD113_M5_NAX_PQ2_DISPATCH_ENQUEUED tg0=%d tg1=%d tg2=%d",
                (ne11 + pipeline.nr1 - 1)/pipeline.nr1,
                (ne01 + pipeline.nr0 - 1)/pipeline.nr0,
                ne12*ne13);
        }

        return 1;
    }

"""
    replace_once(
        ops_cpp,
        '#include <cstdlib>\n#include "ggml-metal-ops.h"\n',
        '#include <cstdlib>\n#include <atomic>\n#include "ggml-metal-ops.h"\n#include "../../../src/bonsai-build84-trace.h"\n',
    )

    replace_once(
        ops_cpp,
        "    if (ggml_metal_op_mul_mat_q1_0_pc_supported(op)) {\n",
        gate + "    if (ggml_metal_op_mul_mat_q1_0_pc_supported(op)) {\n",
    )

    mm_metal.write_text(
        mm_metal.read_text(encoding="utf-8").rstrip() + "\n\n" + KERNEL.lstrip(),
        encoding="utf-8",
    )

    checks = {
        impl_h: ["BONSAI_M5_NAX_PQ2_BM", "BONSAI_M5_NAX_PQ2_BN", "BONSAI_M5_NAX_PQ2_NSG"],
        device_h: ["ggml_metal_library_get_pipeline_mul_mm_nax_pq2"],
        device_cpp: ["kernel_mul_mm_nax_pq2_0_f32", "BONSAI_M5_NAX_PQ2_BN"],
        ops_cpp: [
            "use_pq2_nax",
            "GGML_METAL_PQ2_NAX_DISABLE",
            'bonsai-build84-trace.h',
            "BUILD113_M5_NAX_PQ2_ROUTE_SELECTED",
            "BUILD113_M5_NAX_PQ2_PIPELINE_READY",
            "BUILD113_M5_NAX_PQ2_DISPATCH_ENQUEUED",
        ],
        mm_metal: [
            "kernel_mul_mm_nax_pq2_0_f32",
            "bonsai_m5_nax_pq2_decode4",
            "get_left_input_cooperative_tensor",
            "max_total_threads_per_threadgroup(256)",
        ],
    }

    for path, needles in checks.items():
        source = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle not in source:
                raise SystemExit(f"missing patch marker {needle!r} in {path}")

    run_git(root, "diff", "--check")
    print(f"{MARKER}: PASS")
    print(f"Prism base: {BASE_SHA}")
    print("Touched: ggml-metal-impl.h, ggml-metal-device.h, ggml-metal-device.cpp, ggml-metal-ops.cpp, kernels/mul_mm.metal")

if __name__ == "__main__":
    main()
