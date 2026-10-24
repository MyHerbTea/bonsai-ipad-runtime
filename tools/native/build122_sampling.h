/* Baseline-only systematic samples, random start per worker/graph. No shared hot totals. */
#include <string.h>
#if defined(__APPLE__)
#include <mach/mach_time.h>
static mach_timebase_info_data_t bonsai_sample_tb={1,1};
static uint64_t bonsai_sample_clock(void) { return mach_absolute_time(); }
static uint64_t bonsai_sample_ns(uint64_t x) { return (uint64_t)(((__uint128_t)x*bonsai_sample_tb.numer)/bonsai_sample_tb.denom); }
#else
#include <time.h>
static uint64_t bonsai_sample_clock(void) { struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint64_t)t.tv_sec*1000000000ull+t.tv_nsec; }
static uint64_t bonsai_sample_ns(uint64_t x) { return x; }
#endif
static atomic_bool bonsai_counting_on=ATOMIC_VAR_INIT(1);
static atomic_bool bonsai_sample_phase=ATOMIC_VAR_INIT(0);
static atomic_int bonsai_sample_period=ATOMIC_VAR_INIT(10000);
static _Atomic(uint64_t) bonsai_sample_epoch=ATOMIC_VAR_INIT(1);
static atomic_int bonsai_sample_overflow=ATOMIC_VAR_INIT(0);
static uint64_t bonsai_sample_calibration_ns=0;
struct bonsai_sample_totals { uint64_t seen,samples,seen_blocks,blocks,unpack_ticks,dot_ticks,flushes,reuse_rows,reuse_blocks,reuse_dot_calls,pad[6]; };
static _Alignas(64) struct bonsai_sample_totals bonsai_sample_slots[64];
static _Thread_local struct bonsai_sample_totals bonsai_sample_tls;
static _Thread_local uint64_t bonsai_sample_sequence;
static _Thread_local int bonsai_sample_slot=-1,bonsai_sample_active=0,bonsai_sample_remaining=1,bonsai_sample_stride=10000;

__attribute__((visibility("default"))) int BonsaiNativeCPUSamplingConfigure(int counting,int period) {
    if ((counting!=0 && counting!=1) || (period!=0 && period!=1000 && period!=10000)) return 0;
    atomic_store(&bonsai_sample_phase,0);
#if defined(__APPLE__)
    mach_timebase_info(&bonsai_sample_tb);
#endif
    memset(bonsai_sample_slots,0,sizeof(bonsai_sample_slots));
    atomic_store(&bonsai_sample_overflow,0);
    atomic_store(&bonsai_sample_period,period);
    atomic_store(&bonsai_counting_on,counting!=0);
    atomic_fetch_add(&bonsai_sample_epoch,1);
    bonsai_sample_calibration_ns=0;
    if(period==0)return 1; /* matched off/off candidate comparison: no segmented timer reads */
    uint64_t ticks=0;
    for (int i=0;i<10000;i++) { uint64_t a=bonsai_sample_clock();uint64_t b=bonsai_sample_clock();ticks+=b-a; }
    bonsai_sample_calibration_ns=bonsai_sample_ns(ticks)/10000;
    return 1;
}
void BonsaiNativeCPUSamplingPhase(int enabled) { atomic_store_explicit(&bonsai_sample_phase,enabled!=0,memory_order_release); }
void BonsaiNativeCPUSamplingEnter(int slot) {
    memset(&bonsai_sample_tls,0,sizeof(bonsai_sample_tls));
    bonsai_sample_slot=slot;
    bonsai_sample_active=atomic_load_explicit(&bonsai_sample_phase,memory_order_acquire);
    if (slot<0 || slot>=64) { if(bonsai_sample_active)atomic_store(&bonsai_sample_overflow,1);bonsai_sample_active=0; }
    bonsai_sample_stride=atomic_load(&bonsai_sample_period);
    uint64_t seed=(++bonsai_sample_sequence)*0x9e3779b97f4a7c15ull ^ ((uint64_t)(slot+1)*0xbf58476d1ce4e5b9ull) ^ atomic_load(&bonsai_sample_epoch);
    seed^=seed>>30;seed*=0xbf58476d1ce4e5b9ull;seed^=seed>>27;
    bonsai_sample_remaining=bonsai_sample_stride>0?1+(int)(seed%(uint64_t)bonsai_sample_stride):1;
}
void BonsaiNativeCPUSamplingLeave(void) {
    if (bonsai_sample_active && bonsai_sample_slot>=0 && bonsai_sample_slot<64) {
        struct bonsai_sample_totals *s=&bonsai_sample_slots[bonsai_sample_slot];
        s->seen+=bonsai_sample_tls.seen;s->samples+=bonsai_sample_tls.samples;
        s->seen_blocks+=bonsai_sample_tls.seen_blocks;s->blocks+=bonsai_sample_tls.blocks;
        s->unpack_ticks+=bonsai_sample_tls.unpack_ticks;s->dot_ticks+=bonsai_sample_tls.dot_ticks;s->flushes++;
        s->reuse_rows+=bonsai_sample_tls.reuse_rows;s->reuse_blocks+=bonsai_sample_tls.reuse_blocks;s->reuse_dot_calls+=bonsai_sample_tls.reuse_dot_calls;
    }
    bonsai_sample_active=0;
}
static int bonsai_sample_next(int n) {
    if (!bonsai_sample_active || bonsai_sample_stride==0) return 0;
    bonsai_sample_tls.seen++;bonsai_sample_tls.seen_blocks+=(uint64_t)(n/128);
    if (--bonsai_sample_remaining>0) return 0;
    bonsai_sample_remaining=bonsai_sample_stride;bonsai_sample_tls.samples++;
    return 1;
}
__attribute__((visibility("default"))) uint64_t BonsaiNativeCPUSamplingCounter(int index) {
    struct bonsai_sample_totals t={0};uint64_t used=0,min_samples=UINT64_MAX;
    for(int i=0;i<64;i++) {
        const struct bonsai_sample_totals *s=&bonsai_sample_slots[i];
        t.seen+=s->seen;t.samples+=s->samples;t.seen_blocks+=s->seen_blocks;t.blocks+=s->blocks;
        t.unpack_ticks+=s->unpack_ticks;t.dot_ticks+=s->dot_ticks;t.flushes+=s->flushes;
        t.reuse_rows+=s->reuse_rows;t.reuse_blocks+=s->reuse_blocks;t.reuse_dot_calls+=s->reuse_dot_calls;
        if(s->seen || s->reuse_rows) {used++;if(s->samples<min_samples)min_samples=s->samples;}
    }
    switch(index) {
        case 0:return t.seen;case 1:return t.samples;case 2:return t.seen_blocks;case 3:return t.blocks;
        case 4:return bonsai_sample_ns(t.unpack_ticks);case 5:return bonsai_sample_ns(t.dot_ticks);
        case 6:return bonsai_sample_calibration_ns;case 7:return atomic_load(&bonsai_sample_period);
        case 8:return atomic_load(&bonsai_counting_on);case 9:return atomic_load(&bonsai_sample_overflow);
        case 10:return used;case 11:return used?min_samples:0;case 12:return t.flushes;
        case 13:return t.reuse_rows;case 14:return t.reuse_blocks;case 15:return t.reuse_dot_calls;
        default:return 0;
    }
}
