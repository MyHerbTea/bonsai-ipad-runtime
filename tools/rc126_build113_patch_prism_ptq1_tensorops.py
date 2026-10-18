#!/usr/bin/env python3
"""Apply the opt-in PTQ1_0 register-decode -> Metal TensorOps matmul candidate."""

from pathlib import Path
import argparse
import re
import subprocess

BASE_SHA = "adfffbe41b2cabcd51fff326ab045662265062bb"
MARKER = "BONSAI_M5_PTQ1_TENSOROPS_01"


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, check=False, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise SystemExit(f"git {' '.join(args)} failed ({result.returncode}): {detail}")
    return result.stdout.strip()



def run_diff_check(root: Path) -> None:
    result = subprocess.run(
        ["git", "diff", "--check"], cwd=root, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    if result.returncode == 0:
        return

    repaired = []
    for message in result.stdout.splitlines():
        match = re.match(r"^(.+?):(\d+): trailing whitespace\.$", message.strip())
        if not match:
            continue
        target = root / match.group(1)
        line_number = int(match.group(2))
        lines = target.read_text(encoding="utf-8").splitlines()
        if 1 <= line_number <= len(lines) and lines[line_number - 1].rstrip() != lines[line_number - 1]:
            lines[line_number - 1] = lines[line_number - 1].rstrip()
            target.write_text("\n".join(lines) + "\n", encoding="utf-8")
            repaired.append(f"{match.group(1)}:{line_number}")

    result = subprocess.run(
        ["git", "diff", "--check"], cwd=root, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    if result.returncode != 0:
        raise SystemExit(f"git diff --check failed ({result.returncode}): {result.stdout.strip()}")
    if repaired:
        print("Whitespace-only patch artifacts normalized: " + ", ".join(repaired))

def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one anchor, found {count}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def derive_ptq1_kernel(mm_text: str) -> str:
    marker = "// BONSAI_M5_NAX_PQ2_01"
    if mm_text.count(marker) != 1:
        raise SystemExit("expected the pinned NAX TensorOps tile scaffold exactly once")
    marker_at = mm_text.index(marker)
    start = mm_text.rfind("#ifdef GGML_METAL_HAS_TENSOR", 0, marker_at)
    if start < 0:
        raise SystemExit("could not locate the TensorOps-gated tile scaffold")
    block = mm_text[start:].rstrip()
    if not block.endswith("#endif // GGML_METAL_HAS_TENSOR"):
        raise SystemExit("expected the NAX TensorOps scaffold to end at the file tail")

    # Reuse only the cooperative-MMA tile/accumulation structure. Replace the
    # packed-weight decoder with Prism's actual PTQ1_0 base-3 codec.
    for old, new in (
        ("BONSAI_M5_NAX_PQ2_01", MARKER),
        ("nax_pq2", "ptq1_tensorops"),
        ("NAX-PQ2", "PTQ1 TensorOps"),
        ("PQ2_0", "PTQ1_0"),
        ("PQ2", "PTQ1"),
        ("pq2", "ptq1"),
        ("block_pq2_0", "block_ptq1_0"),
        ("QK_PQ2_0", "QK_PTQ1_0"),
    ):
        block = block.replace(old, new)

    decoder_start = block.find("static inline half4 bonsai_m5_ptq1_tensorops_decode4(")
    if decoder_start < 0:
        raise SystemExit("transformed PTQ1 decoder signature missing")
    decoder_end = block.find("\n}\n", decoder_start)
    if decoder_end < 0:
        raise SystemExit("transformed PTQ1 decoder body missing")
    decoder_end += 3
    decoder = r'''static inline half4 bonsai_m5_ptq1_tensorops_decode4(
        device const block_ptq1_0 * row_blocks,
        int kpos) {
    const int block_index = kpos / QK_PTQ1_0;
    const int in_block = kpos - block_index * QK_PTQ1_0;
    device const block_ptq1_0 * block = row_blocks + block_index;
    const float d = block->d;
    half4 decoded;

    // Match Prism dequantize_ptq1_0 exactly using its real base-3 lookup table.
    for (short i = 0; i < 4; ++i) {
        const int e = in_block + i;
        uchar b;
        short n;
        if (e < 80) {
            b = block->qs[e & 15];
            n = e >> 4;
        } else if (e < 120) {
            const int t = e - 80;
            b = block->qs[16 + (t & 7)];
            n = t >> 3;
        } else {
            const int t = e - 120;
            b = block->qh[t & 1];
            n = t >> 1;
        }
        const int trit = (int)((ptq1_0_lut[b] >> (2 * n)) & 3) - 1;
        decoded[i] = half((float)trit * d);
    }
    return decoded;
}'''
    block = block[:decoder_start] + decoder + block[decoder_end:]
    if "block_pq2_0" in block or "QK_PQ2_0" in block:
        raise SystemExit("PTQ1 kernel still contains PQ2 layout references")
    if "ptq1_0_lut[b]" not in block:
        raise SystemExit("PTQ1 kernel does not use Prism's PTQ1_0 lookup table")
    if "kernel_mul_mm_ptq1_tensorops_0_f32" not in block:
        raise SystemExit("PTQ1 kernel host name missing")
    block = "\n".join(line.rstrip() for line in block.splitlines())
    return "\n\n" + block + "\n"


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
    mm_text = mm_metal.read_text(encoding="utf-8")
    if MARKER in mm_text:
        raise SystemExit("PTQ1 TensorOps patch already applied")
    kernel = derive_ptq1_kernel(mm_text)

    replace_once(
        impl_h,
        "#define BONSAI_M5_NAX_PQ2_NSG 4\n",
        "#define BONSAI_M5_NAX_PQ2_NSG 4\n"
        "// BONSAI_M5_PTQ1_TENSOROPS_01: opt-in PTQ1_0 16x128 tile.\n"
        "#define BONSAI_M5_PTQ1_TENSOROPS_BM 16\n"
        "#define BONSAI_M5_PTQ1_TENSOROPS_BN 128\n"
        "#define BONSAI_M5_PTQ1_TENSOROPS_QK 128\n"
        "#define BONSAI_M5_PTQ1_TENSOROPS_NSG 4\n",
    )
    replace_once(
        device_h,
        "struct ggml_metal_pipeline_with_params ggml_metal_library_get_pipeline_mul_mm_nax_pq2(ggml_metal_library_t lib);\n",
        "struct ggml_metal_pipeline_with_params ggml_metal_library_get_pipeline_mul_mm_nax_pq2(ggml_metal_library_t lib);\n"
        "struct ggml_metal_pipeline_with_params ggml_metal_library_get_pipeline_mul_mm_ptq1_tensorops(ggml_metal_library_t lib);\n",
    )
    getter = r'''
struct ggml_metal_pipeline_with_params ggml_metal_library_get_pipeline_mul_mm_ptq1_tensorops(ggml_metal_library_t lib) {
    const char * name = "kernel_mul_mm_ptq1_tensorops_0_f32";
    ggml_metal_pipeline_with_params res = ggml_metal_library_get_pipeline(lib, name);
    if (!res.pipeline) {
        res = ggml_metal_library_compile_pipeline(lib, name, name, nullptr);
    }
    res.nr0 = BONSAI_M5_PTQ1_TENSOROPS_BN;
    res.nr1 = BONSAI_M5_PTQ1_TENSOROPS_BM;
    res.nsg = BONSAI_M5_PTQ1_TENSOROPS_NSG;
    res.smem = 0;
    return res;
}

'''
    getter = "\n".join(line.rstrip() for line in getter.splitlines()) + "\n"
    replace_once(
        device_cpp,
        "struct ggml_metal_pipeline_with_params ggml_metal_library_get_pipeline_mul_mm_nax_pq2(ggml_metal_library_t lib) {\n",
        getter + "struct ggml_metal_pipeline_with_params ggml_metal_library_get_pipeline_mul_mm_nax_pq2(ggml_metal_library_t lib) {\n",
    )
    trace_helper = r'''
static inline void bonsai_m5_ptq1_tensor_trace(const char *fmt, ...) {
    const char *path = std::getenv("BONSAI_M5_PTQ1_TENSOR_TRACE_PATH");
    if (!path || !*path) { return; }
    char line[320];
    va_list ap;
    va_start(ap, fmt);
    int n = std::vsnprintf(line, sizeof(line) - 2, fmt, ap);
    va_end(ap);
    if (n <= 0) { return; }
    size_t size = (size_t)n < sizeof(line) - 2 ? (size_t)n : sizeof(line) - 2;
    line[size++] = '\n';
    int fd = ::open(path, O_CREAT | O_APPEND | O_WRONLY, 0600);
    if (fd < 0) { return; }
    size_t done = 0;
    while (done < size) {
        ssize_t count = ::write(fd, line + done, size - done);
        if (count <= 0) { break; }
        done += (size_t)count;
    }
    ::fsync(fd);
    ::close(fd);
}
'''
    trace_helper = "\n".join(line.rstrip() for line in trace_helper.splitlines()) + "\n"
    replace_once(
        ops_cpp,
        "int ggml_metal_op_mul_mat(ggml_metal_op_t ctx, int idx) {\n",
        trace_helper + "\nint ggml_metal_op_mul_mat(ggml_metal_op_t ctx, int idx) {\n",
    )
    gate = r'''
    // BONSAI_M5_PTQ1_TENSOROPS_01:
    // Record actual operand types in both A/B arms; candidate markers are separate.
    if (std::getenv("BONSAI_M5_PTQ1_TENSOR_TRACE_PATH") != nullptr &&
        op->src[0]->type == GGML_TYPE_PTQ1_0 && op->src[1]->type == GGML_TYPE_F32) {
        static std::atomic_flag ptq1_input_type_trace_once = ATOMIC_FLAG_INIT;
        if (!ptq1_input_type_trace_once.test_and_set(std::memory_order_relaxed)) {
            bonsai_m5_ptq1_tensor_trace(
                "BUILD113_PTQ1_TENSOROPS_INPUT_TYPE_OBSERVED weight_type=%d activation_type=%d output_type=%d K=%d M=%d N=%d",
                (int) op->src[0]->type, (int) op->src[1]->type, (int) op->type,
                ne00, ne11, ne01);
        }
    }
    // Candidate pipeline failure is traced and falls back to inherited Prism dispatch.
    static const bool ptq1_tensorops_disabled =
        std::getenv("GGML_METAL_PTQ1_TENSOROPS_DISABLE") != nullptr;
    static std::atomic_bool ptq1_tensorops_pipeline_failed{false};
    const bool use_ptq1_tensorops =
        !ptq1_tensorops_disabled &&
        !ptq1_tensorops_pipeline_failed.load(std::memory_order_relaxed) &&
        props_dev->has_tensor &&
        props_dev->has_simdgroup_mm &&
        props_dev->device_id >= GGML_METAL_DEVICE_M5 &&
        op->src[0]->type == GGML_TYPE_PTQ1_0 &&
        op->src[1]->type == GGML_TYPE_F32 &&
        op->type == GGML_TYPE_F32 &&
        !ggml_is_transposed(op->src[0]) &&
        !ggml_is_transposed(op->src[1]) &&
        ne00 % BONSAI_M5_PTQ1_TENSOROPS_QK == 0 &&
        ne11 >= BONSAI_M5_PTQ1_TENSOROPS_BM &&
        ne11 % BONSAI_M5_PTQ1_TENSOROPS_BM == 0 &&
        ne01 >= BONSAI_M5_PTQ1_TENSOROPS_BN &&
        ne02 == 1 && ne03 == 1 &&
        ne12 == 1 && ne13 == 1 &&
        nb10 == sizeof(float) &&
        op->nb[0] == sizeof(float) &&
        op->nb[1] == op->ne[0] * sizeof(float) &&
        nb01 % ggml_type_size(GGML_TYPE_PTQ1_0) == 0;

    if (use_ptq1_tensorops) {
        static std::atomic_flag ptq1_trace_once = ATOMIC_FLAG_INIT;
        const bool trace_this_dispatch =
            std::getenv("BONSAI_M5_PTQ1_TENSOR_TRACE_PATH") != nullptr &&
            !ptq1_trace_once.test_and_set(std::memory_order_relaxed);
        if (trace_this_dispatch) {
            bonsai_m5_ptq1_tensor_trace(
                "BUILD113_PTQ1_TENSOROPS_ROUTE_SELECTED weight_type=%d activation_type=%d K=%d M=%d N=%d",
                (int) op->src[0]->type, (int) op->src[1]->type, ne00, ne11, ne01);
        }

        const auto pipeline = ggml_metal_library_get_pipeline_mul_mm_ptq1_tensorops(lib);
        if (!pipeline.pipeline) {
            ptq1_tensorops_pipeline_failed.store(true, std::memory_order_relaxed);
            if (trace_this_dispatch) {
                bonsai_m5_ptq1_tensor_trace("BUILD113_PTQ1_TENSOROPS_PIPELINE_READY ok=0");
                bonsai_m5_ptq1_tensor_trace(
                    "BUILD113_PTQ1_TENSOROPS_FALLBACK_TO_PRISM reason=pipeline_not_ready");
            }
            return 0;
        }
        if (trace_this_dispatch) {
            bonsai_m5_ptq1_tensor_trace(
                "BUILD113_PTQ1_TENSOROPS_PIPELINE_READY ok=1 nr0=%d nr1=%d nsg=%d",
                pipeline.nr0, pipeline.nr1, pipeline.nsg);
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
        ggml_metal_encoder_set_bytes(enc, &args, sizeof(args), 0);
        ggml_metal_encoder_set_buffer(enc, ggml_metal_get_buffer_id(op->src[0]), 1);
        ggml_metal_encoder_set_buffer(enc, ggml_metal_get_buffer_id(op->src[1]), 2);
        ggml_metal_encoder_set_buffer(enc, ggml_metal_get_buffer_id(op), 3);
        ggml_metal_encoder_set_threadgroup_memory_size(enc, pipeline.smem, 0);
        const int tg0 = (ne11 + pipeline.nr1 - 1) / pipeline.nr1;
        const int tg1 = (ne01 + pipeline.nr0 - 1) / pipeline.nr0;
        const int tg2 = ne12 * ne13;
        ggml_metal_encoder_dispatch_threadgroups(
            enc, tg0, tg1, tg2, 32, pipeline.nsg, 1);
        if (trace_this_dispatch) {
            bonsai_m5_ptq1_tensor_trace(
                "BUILD113_PTQ1_TENSOROPS_DISPATCH_ENQUEUED tg0=%d tg1=%d tg2=%d",
                tg0, tg1, tg2);
        }
        return 1;
    }

'''
    gate = "\n".join(line.rstrip() for line in gate.splitlines()) + "\n"
    replace_once(
        ops_cpp,
        "    if (ggml_metal_op_mul_mat_q1_0_pc_supported(op)) {\n",
        gate + "    if (ggml_metal_op_mul_mat_q1_0_pc_supported(op)) {\n",
    )
    mm_metal.write_text(mm_text.rstrip() + kernel, encoding="utf-8")

    checks = {
        impl_h: ["BONSAI_M5_PTQ1_TENSOROPS_BM", "BONSAI_M5_PTQ1_TENSOROPS_BN", "BONSAI_M5_PTQ1_TENSOROPS_QK"],
        device_h: ["ggml_metal_library_get_pipeline_mul_mm_ptq1_tensorops"],
        device_cpp: ["kernel_mul_mm_ptq1_tensorops_0_f32", "BONSAI_M5_PTQ1_TENSOROPS_BN"],
        ops_cpp: [
            "GGML_TYPE_PTQ1_0", "op->src[1]->type == GGML_TYPE_F32",
            "GGML_METAL_PTQ1_TENSOROPS_DISABLE",
            "BUILD113_PTQ1_TENSOROPS_INPUT_TYPE_OBSERVED",
            "BUILD113_PTQ1_TENSOROPS_ROUTE_SELECTED",
            "BUILD113_PTQ1_TENSOROPS_PIPELINE_READY",
            "BUILD113_PTQ1_TENSOROPS_DISPATCH_ENQUEUED",
            "BUILD113_PTQ1_TENSOROPS_FALLBACK_TO_PRISM",
        ],
        mm_metal: [MARKER, "ptq1_0_lut[b]", "block_ptq1_0",
                   "kernel_mul_mm_ptq1_tensorops_0_f32",
                   "get_left_input_cooperative_tensor"],
    }
    for path, needles in checks.items():
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                raise SystemExit(f"missing PTQ1 patch marker {needle!r} in {path}")
    run_diff_check(root)
    print(f"{MARKER}: PASS")
    print(f"Prism base: {BASE_SHA}")
    print("PTQ1 route: actual weight type + F32 activation + M5 + K%128 + M%16")
    print("Decode: Prism ptq1_0_lut trits -> half4 registers -> cooperative TensorOps MMA")
    print("Pipeline compile failure is traced and falls back to inherited Prism dispatch")


if __name__ == "__main__":
    main()
