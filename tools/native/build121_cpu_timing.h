/* Benchmark-prefill CPU node wall intervals, one threadpool leader only. */
#include <stdatomic.h>
#include <stdint.h>
#if defined(__APPLE__)
#include <mach/mach_time.h>
static mach_timebase_info_data_t bonsai_cpu_timebase = {1,1};
static uint64_t bonsai_cpu_clock(void) { return mach_absolute_time(); }
#else
#include <time.h>
static uint64_t bonsai_cpu_clock(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec*1000000000ull + (uint64_t)t.tv_nsec;
}
#endif
static atomic_bool bonsai_cpu_time_enabled = ATOMIC_VAR_INIT(0);
static _Atomic(uint64_t) bonsai_cpu_time_counts[8];

__attribute__((visibility("default"))) void BonsaiNativeCPUTimeEnable(int enabled) {
#if defined(__APPLE__)
    if (enabled) mach_timebase_info(&bonsai_cpu_timebase);
#endif
    atomic_store_explicit(&bonsai_cpu_time_enabled, enabled != 0, memory_order_release);
}
__attribute__((visibility("default"))) void BonsaiNativeCPUTimeReset(void) {
    atomic_store_explicit(&bonsai_cpu_time_enabled, 0, memory_order_release);
    for (int i=0;i<8;i++) atomic_store_explicit(&bonsai_cpu_time_counts[i],0,memory_order_relaxed);
}
__attribute__((visibility("default"))) uint64_t BonsaiNativeCPUTimeCounter(int index) {
    return index>=0 && index<8 ? atomic_load_explicit(&bonsai_cpu_time_counts[index],memory_order_acquire) : 0;
}
static uint64_t bonsai_cpu_time_begin(void) {
    return atomic_load_explicit(&bonsai_cpu_time_enabled,memory_order_acquire) ? bonsai_cpu_clock() : 0;
}
static void bonsai_cpu_time_end(int category,uint64_t began) {
    if (!began || category<0 || category>=4) return;
    const uint64_t ended = bonsai_cpu_clock();
    if (ended<began) return;
    uint64_t ns = ended-began;
#if defined(__APPLE__)
    ns = (uint64_t)(((__uint128_t)ns*bonsai_cpu_timebase.numer)/bonsai_cpu_timebase.denom);
#endif
    atomic_fetch_add_explicit(&bonsai_cpu_time_counts[category],ns,memory_order_relaxed);
    atomic_fetch_add_explicit(&bonsai_cpu_time_counts[category+4],1,memory_order_relaxed);
}
