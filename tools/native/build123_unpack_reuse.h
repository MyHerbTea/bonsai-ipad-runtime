/* flag17 (wire32): baseline arithmetic; decode a block once for <=8 Q8 columns. */
__attribute__((visibility("default"))) int BonsaiNativeCPUReuseEnabled(void) {
    return atomic_load_explicit(&bonsai_cpu_flags,memory_order_relaxed)==32 &&
        !atomic_load_explicit(&bonsai_counting_on,memory_order_relaxed);
}
__attribute__((visibility("default"))) void BonsaiNativeCPUReuseRow(
        int n,float * dst,size_t dst_stride,const void * vx,const void * vy,size_t y_stride,int columns) {
    assert(n>0 && n%128==0 && columns>=2 && columns<=8);
    const block_ptq1_0 * GGML_RESTRICT x=vx;
    const int nb=n/128;
    float sumf[8]={0};
    static const uint8_t pow3[6]={1,3,9,27,81,243};
    static const size_t stages[3]={32,16,8};
    for(int i=0;i<nb;i++) {
        int8_t q[128];int o=0;size_t j=0;
        for(size_t st=0;st<3;st++) {
            const size_t c=stages[st];
            for(;j+c<=sizeof(x->qs);j+=c)
                for(size_t nn=0;nn<5;nn++)
                    for(size_t m=0;m<c;m++) {
                        const uint8_t v=x[i].qs[j+m]*pow3[nn];
                        const int16_t xi=((uint16_t)v*3)>>8;
                        q[o++]=(int8_t)(xi-1);
                    }
        }
        for(size_t nn=0;nn<4;nn++)
            for(size_t h=0;h<sizeof(x->qh);h++) {
                const uint8_t v=x[i].qh[h]*pow3[nn];
                const int16_t xi=((uint16_t)v*3)>>8;
                q[o++]=(int8_t)(xi-1);
            }
        assert(o==128);
        const float d0=GGML_CPU_FP16_TO_FP32(x[i].d);
        for(int column=0;column<columns;column++) {
            const block_q8_0 * GGML_RESTRICT y=(const block_q8_0 *)((const char *)vy+column*y_stride);
            float sumi=0.0f;
            for(int k=0;k<4;k++) {
                const block_q8_0 * GGML_RESTRICT yb=&y[i*4+k];
                const float d1=GGML_CPU_FP16_TO_FP32(yb->d);
                int sumi_block=0;
                for(int b=0;b<32;b++)sumi_block+=(int)q[k*32+b]*(int)yb->qs[b];
                sumi+=d1*sumi_block;
            }
            sumf[column]+=d0*sumi;
        }
    }
    for(int column=0;column<columns;column++)*(float *)((char *)dst+column*dst_stride)=sumf[column];
    if(bonsai_sample_active) {
        bonsai_sample_tls.reuse_rows++;
        bonsai_sample_tls.reuse_blocks+=(uint64_t)nb;
        bonsai_sample_tls.reuse_dot_calls+=(uint64_t)columns;
    }
}
