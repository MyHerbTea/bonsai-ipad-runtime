"""Build125: two adjacent weight rows, one Q8 input column. Apply after124."""
from pathlib import Path
import argparse
from rc126_build113_patch_prism_ptq1_tensorops import BASE_SHA,run_git,replace_once,run_diff_check

CONTROL = '''// BONSAI_SDOT_PAIR_125: identical off-control once per logical row in A/B/C.
__attribute__((noinline)) static int bonsai_ptq1_off_control(int n) {
    if (atomic_load_explicit(&bonsai_counting_on,memory_order_relaxed) ||
        atomic_load_explicit(&bonsai_sample_period,memory_order_relaxed)!=0) return 0;
    (void)bonsai_sample_next(n);
    return 1;
}
__attribute__((visibility("default"))) int BonsaiNativeCPUSDOTPairEnabled(void) {
    return BONSAI_CPU_SDOT && atomic_load_explicit(&bonsai_cpu_flags,memory_order_relaxed)==128 &&
        !atomic_load_explicit(&bonsai_counting_on,memory_order_relaxed) &&
        atomic_load_explicit(&bonsai_sample_period,memory_order_relaxed)==0;
}
__attribute__((visibility("default"))) void BonsaiNativeCPUSDOTPairObserve(int64_t rows) {
    if (bonsai_sample_active && rows>0) {
        bonsai_sample_tls.pair_chunks++;
        bonsai_sample_tls.pair_rows+=(uint64_t)rows;
    }
}
#if BONSAI_CPU_SDOT
'''
PAIR = '''
__attribute__((target("dotprod"),noinline,visibility("default")))
int BonsaiNativeCPUSDOTPair(int n,float * restrict s0,float * restrict s1,
        const void * restrict vx0,const void * restrict vx1,const void * restrict vy) {
    assert(n>=0 && n%128==0);
    if (!bonsai_ptq1_off_control(n) || !bonsai_ptq1_off_control(n)) return 0;
    const block_ptq1_0 * restrict x0=vx0,* restrict x1=vx1;
    const block_q8_0 * restrict y=vy;
    float sumf0=0.0f,sumf1=0.0f;
    for (int i=0;i<n/128;i++) {
        int8_t q0[128],q1[128];
        bonsai_pair_decode_125(x0+i,q0);
        bonsai_pair_decode_125(x1+i,q1);
        const float d0=GGML_CPU_FP16_TO_FP32(x0[i].d);
        const float d1=GGML_CPU_FP16_TO_FP32(x1[i].d);
        float sumi0=0.0f,sumi1=0.0f;
        for (int k=0;k<4;k++) {
            const block_q8_0 * restrict yb=y+i*4+k;
            const float dy=GGML_CPU_FP16_TO_FP32(yb->d);
            const int8x16_t yl=vld1q_s8(yb->qs),yh=vld1q_s8(yb->qs+16);
            int32x4_t a=vdupq_n_s32(0),b=vdupq_n_s32(0);
            a=vdotq_s32(a,vld1q_s8(q0+k*32),yl);
            a=vdotq_s32(a,vld1q_s8(q0+k*32+16),yh);
            b=vdotq_s32(b,vld1q_s8(q1+k*32),yl);
            b=vdotq_s32(b,vld1q_s8(q1+k*32+16),yh);
            sumi0+=dy*vaddvq_s32(a);
            sumi1+=dy*vaddvq_s32(b);
        }
        sumf0+=d0*sumi0;
        sumf1+=d1*sumi1;
    }
    *s0=sumf0;*s1=sumf1;
    return 1;
}
#else
__attribute__((visibility("default")))
int BonsaiNativeCPUSDOTPair(int n,float *s0,float *s1,const void *x0,const void *x1,const void *y) {
    (void)n;(void)s0;(void)s1;(void)x0;(void)x1;(void)y;return 0;
}
#endif
'''

def instrument_quants(s):
    if 'BONSAI_SDOT_PAIR_125' in s:raise ValueError('already patched125')
    start=s.index('void ggml_vec_dot_ptq1_0_q8_0_generic(')
    math=s.index('    static const uint8_t pow3[6]',start)
    decode_start=s.index('        int o = 0;',math)
    decode_end=s.index('        assert(o == QK_PTQ1_0);',decode_start)+len('        assert(o == QK_PTQ1_0);')
    decoder=s[math:s.index('    float sumf = 0.0f;',math)]+s[decode_start:decode_end]
    decoder=decoder.replace('x[i].','x->')
    decoder='static inline __attribute__((always_inline)) void bonsai_pair_decode_125(const block_ptq1_0 *x,int8_t q[128]) {\n'+decoder+'\n}\n'
    entry='''    if ((bonsai_flags==0 || bonsai_flags==64 || bonsai_flags==128) && bonsai_ptq1_off_control(n)) {
#if BONSAI_CPU_SDOT
        if (bonsai_flags!=0) { bonsai_sdot_ptq1_dot(n,s,bs,vx,bx,vy,by,nrc);return; }
#endif
        goto bonsai_off_baseline_125;
    }
'''
    anchor='    const int bonsai_flags = atomic_load_explicit(&bonsai_cpu_flags, memory_order_relaxed);'
    head=s[start:math]
    assert head.count(anchor)==1
    head=head.replace(anchor,anchor+'\n'+entry,1)
    head=head.replace('if (bonsai_flags == 64)', 'if (bonsai_flags == 64 || bonsai_flags == 128)')
    return s[:start]+CONTROL+decoder+PAIR+head+'bonsai_off_baseline_125: ;\n'+s[math:]


def instrument_cpu(s):
    if 'BONSAI_SDOT_PAIR_ROUTE_125' in s:raise ValueError('already routed125')
    anchor='                for (int64_t ir0 = iir0; ir0 < iir0 + blck_0 && ir0 < ir0_end; ir0 += num_rows_per_vec_dot) {'
    assert s.count(anchor)==1
    route='''                // BONSAI_SDOT_PAIR_ROUTE_125: preserve column order, tmp layout and tail.
                int64_t bonsai_pair_row=iir0;
                if (src0->type==GGML_TYPE_PTQ1_0 && vec_dot_type==GGML_TYPE_Q8_0 &&
                    num_rows_per_vec_dot==1 && ne00>0 && ne00<=INT_MAX && ne00%128==0 &&
                    nb00==ggml_type_size(GGML_TYPE_PTQ1_0) && nb01>=ggml_row_size(GGML_TYPE_PTQ1_0,ne00) &&
                    nb0==sizeof(float) && ne11 > 1 && ne11 <= 8 && BonsaiNativeCPUSDOTPairEnabled()) {
                    for (; bonsai_pair_row + 1 < MIN(iir0+blck_0,ir0_end);bonsai_pair_row+=2) {
                        if (!BonsaiNativeCPUSDOTPair((int)ne00,&tmp[bonsai_pair_row-iir0],&tmp[bonsai_pair_row-iir0+1],
                            src0_row+bonsai_pair_row*nb01,src0_row+(bonsai_pair_row+1)*nb01,src1_col)) break;
                    }
                    if (bonsai_pair_row>iir0) BonsaiNativeCPUSDOTPairObserve(bonsai_pair_row-iir0);
                }
'''
    s=s.replace(anchor,route+anchor.replace('ir0 = iir0','ir0 = bonsai_pair_row'),1)
    anchor='#include "common.h"'
    assert s.count(anchor)==1
    return s.replace(anchor,anchor+'\n#include <limits.h>\nint BonsaiNativeCPUSDOTPairEnabled(void);\nint BonsaiNativeCPUSDOTPair(int,float *,float *,const void *,const void *,const void *);\nvoid BonsaiNativeCPUSDOTPairObserve(int64_t);',1)


def apply(root):
    if run_git(root,'rev-parse','HEAD')!=BASE_SHA:raise ValueError('wrong Prism base')
    cpu=root/'ggml/src/ggml-cpu'
    p=cpu/'quants.c';p.write_text(instrument_quants(p.read_text(encoding='utf-8')),encoding='utf-8')
    p=cpu/'ggml-cpu.c';p.write_text(instrument_cpu(p.read_text(encoding='utf-8')),encoding='utf-8')
    p=cpu/'build122_sampling.h';s=p.read_text(encoding='utf-8')
    s=s.replace('reuse_dot_calls,pad[6]','reuse_dot_calls,pair_chunks,pair_rows,pad[4]')
    s=s.replace('s->reuse_dot_calls+=bonsai_sample_tls.reuse_dot_calls;','s->reuse_dot_calls+=bonsai_sample_tls.reuse_dot_calls;\n        s->pair_chunks+=bonsai_sample_tls.pair_chunks;s->pair_rows+=bonsai_sample_tls.pair_rows;')
    s=s.replace('t.reuse_dot_calls+=s->reuse_dot_calls;','t.reuse_dot_calls+=s->reuse_dot_calls;\n        t.pair_chunks+=s->pair_chunks;t.pair_rows+=s->pair_rows;')
    s=s.replace('case 15:return t.reuse_dot_calls;','case 15:return t.reuse_dot_calls;case 16:return t.pair_chunks;case 17:return t.pair_rows;')
    p.write_text(s,encoding='utf-8')
    replace_once(cpu/'build118_ptq1_cpu.h','(bonsai_sdot_supported() ? 64u : 0u)','(bonsai_sdot_supported() ? 192u : 0u)')
    replace_once(cpu/'build118_ptq1_cpu.h','if (flags==64 && !bonsai_sdot_supported())','if ((flags==64 || flags==128) && !bonsai_sdot_supported())')
    replace_once(root/'ggml/src/ggml-metal/ggml-metal-ops.cpp','if (flags != 32 && flags != 64 && (flags < -1','if (flags != 32 && flags != 64 && flags != 128 && (flags < -1')
    run_diff_check(root)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);apply(p.parse_args().root)
