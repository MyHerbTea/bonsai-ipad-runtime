/* Opt-in PTQ1 CPU candidates. Included once by ggml-cpu/quants.c. */
#include <stdatomic.h>
#include <stdint.h>
#if defined(__ARM_NEON) || defined(__ARM_NEON__)
#include <arm_neon.h>
#define BONSAI_CPU_NEON 1
#else
#define BONSAI_CPU_NEON 0
#endif

static const int8_t bonsai_trits[256][5] = {
#include "build118_ptq1_lut.inc"
};
static atomic_int bonsai_cpu_flags = ATOMIC_VAR_INIT(-1);
static _Atomic(uint64_t) bonsai_cpu_calls[3];

__attribute__((visibility("default"))) uint32_t BonsaiNativeCPUCapabilities(void) {
    return 8u | (BONSAI_CPU_NEON ? 16u : 0u);
}
__attribute__((visibility("default"))) void BonsaiNativeCPUConfigure(int flags) {
    atomic_store_explicit(&bonsai_cpu_flags, flags, memory_order_release);
}
__attribute__((visibility("default"))) uint64_t BonsaiNativeCPUCounter(int index) {
    return index >= 0 && index < 3 ? atomic_load_explicit(&bonsai_cpu_calls[index], memory_order_relaxed) : 0;
}
__attribute__((visibility("default"))) void BonsaiNativeCPUBeginRequest(void) {
    for (int i = 0; i < 3; ++i) atomic_store_explicit(&bonsai_cpu_calls[i], 0, memory_order_relaxed);
}

static void bonsai_cpu_decode(const block_ptq1_0 * x, int8_t q[128], int neon) {
    int output = 0;
    /* Format order: 16 packed bytes x5, then 8 x5, then 2 high bytes x4. */
    for (int stage = 0; stage < 2; ++stage) {
        const int count = stage == 0 ? 16 : 8;
        const uint8_t * input = x->qs + (stage == 0 ? 0 : 16);
        for (int digit = 0, factor = 1; digit < 5; ++digit, factor *= 3) {
#if BONSAI_CPU_NEON
            if (neon) {
                if (count == 16) {
                    const uint8x16_t v = vmulq_u8(vld1q_u8(input), vdupq_n_u8((uint8_t)factor));
                    const uint8x8_t lo = vshrn_n_u16(vmull_u8(vget_low_u8(v), vdup_n_u8(3)), 8);
                    const uint8x8_t hi = vshrn_n_u16(vmull_u8(vget_high_u8(v), vdup_n_u8(3)), 8);
                    vst1q_s8(q + output, vsubq_s8(vreinterpretq_s8_u8(vcombine_u8(lo, hi)), vdupq_n_s8(1)));
                } else {
                    const uint8x8_t v = vmul_u8(vld1_u8(input), vdup_n_u8((uint8_t)factor));
                    vst1_s8(q + output, vsub_s8(vreinterpret_s8_u8(vshrn_n_u16(vmull_u8(v, vdup_n_u8(3)), 8)), vdup_n_s8(1)));
                }
            } else
#else
            (void)neon;
#endif
            {
                for (int m = 0; m < count; ++m) q[output + m] = bonsai_trits[input[m]][digit];
            }
            output += count;
        }
    }
    for (int digit = 0; digit < 4; ++digit)
        for (int m = 0; m < 2; ++m) q[output++] = bonsai_trits[x->qh[m]][digit];
    assert(output == 128);
}

static int bonsai_cpu_dot32(const int8_t * q, const int8_t * y, int neon) {
#if BONSAI_CPU_NEON
    if (neon) {
        int32x4_t sum = vdupq_n_s32(0);
        for (int i = 0; i < 32; i += 8)
            sum = vpadalq_s16(sum, vmull_s8(vld1_s8(q + i), vld1_s8(y + i)));
        return vaddvq_s32(sum);
    }
#else
    (void)neon;
#endif
    int sum = 0;
    for (int i = 0; i < 32; ++i) sum += (int)q[i] * (int)y[i];
    return sum;
}

static float bonsai_cpu_dot(int n, const block_ptq1_0 * x, const block_q8_0 * y, int neon) {
    float sumf = 0.0f;
    for (int i = 0; i < n / 128; ++i) {
        int8_t q[128];
        bonsai_cpu_decode(&x[i], q, neon);
        const float d0 = GGML_CPU_FP16_TO_FP32(x[i].d);
        float sumi = 0.0f;
        for (int k = 0; k < 4; ++k) {
            const block_q8_0 * yb = &y[i*4+k];
            const float d1 = GGML_CPU_FP16_TO_FP32(yb->d);
            const int integer_dot = bonsai_cpu_dot32(q + k*32, yb->qs, neon);
            sumi += d1 * integer_dot;
        }
        sumf += d0 * sumi;
    }
    return sumf;
}
