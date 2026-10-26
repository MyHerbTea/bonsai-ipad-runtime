#pragma once
#include <stdint.h>

// Keep the Build125 CPU SDOT control active while stripping only the new
// Metal-only capability bit before forwarding flags to the CPU path.
static inline int32_t bonsai_q8_metal_b8_cpu_flags(int32_t flags) {
    return flags < 0 ? flags : (int32_t)((uint32_t)flags & ~256u);
}

static inline bool bonsai_q8_metal_b8_eligible(
        int32_t flags, bool m5, bool ptq1, bool act_f32, bool out_f32,
        bool contiguous, bool shape_ok, int64_t ne11) {
    return flags == 320 && m5 && ptq1 && act_f32 && out_f32 &&
        contiguous && shape_ok && ne11 == 8;
}