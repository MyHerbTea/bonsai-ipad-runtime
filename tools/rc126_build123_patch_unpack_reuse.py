"""Apply after122. New candidate32 alone; no scheduler/barrier/weight-placement change."""
from pathlib import Path
import argparse
from rc126_build113_patch_prism_ptq1_tensorops import BASE_SHA,run_git,run_diff_check,replace_once

ROUTE='''            // BONSAI_UNPACK_REUSE_123: eligible current columns share one128-trit scratch.
            const int64_t columns=MIN(iir1+blck_1,ir1_end)-iir1;
            if (src0->type == GGML_TYPE_PTQ1_0 && vec_dot_type == GGML_TYPE_Q8_0 &&
                num_rows_per_vec_dot == 1 && ne00 > 0 && ne00 <= INT_MAX && ne00 % 128 == 0 &&
                nb00 == ggml_type_size(GGML_TYPE_PTQ1_0) && nb01 >= ggml_row_size(GGML_TYPE_PTQ1_0,ne00) &&
                nb0 == sizeof(float) && columns >= 2 && columns <= 8 &&
                iir1/ne1 == (iir1+columns-1)/ne1 && BonsaiNativeCPUReuseEnabled()) {
                const int64_t i13=iir1/(ne12*ne1);
                const int64_t i12=(iir1-i13*ne12*ne1)/ne1;
                const int64_t i11=iir1-i13*ne12*ne1-i12*ne1;
                const char * weight=(const char *)src0->data+(i12/r2)*nb02+(i13/r3)*nb03;
                const char * input=(const char *)wdata+(src1_cont || src1->type != vec_dot_type
                    ? (i11+i12*ne11+i13*ne12*ne11)*row_size : i11*nb11+i12*nb12+i13*nb13);
                float * output=(float *)((char *)dst->data+i11*nb1+i12*nb2+i13*nb3);
                for(int64_t row=iir0;row<MIN(iir0+blck_0,ir0_end);row++)
                    BonsaiNativeCPUReuseRow((int)ne00,output+row,nb1,weight+row*nb01,input,src1_col_stride,(int)columns);
                continue;
            }
'''

def instrument_cpu(s):
    if 'BONSAI_UNPACK_REUSE_123' in s:raise ValueError('already patched123')
    anchor='            for (int64_t ir1 = iir1; ir1 < iir1 + blck_1 && ir1 < ir1_end; ir1 += num_rows_per_vec_dot) {'
    assert s.count(anchor)==1
    s=s.replace(anchor,ROUTE+anchor,1)
    anchor='#include "common.h"'
    assert s.count(anchor)==1
    return s.replace(anchor,anchor+'\n#include <limits.h>\nint BonsaiNativeCPUReuseEnabled(void);\nvoid BonsaiNativeCPUReuseRow(int,float *,size_t,const void *,const void *,size_t,int);',1)

def apply(root):
    if run_git(root,'rev-parse','HEAD')!=BASE_SHA:raise ValueError('wrong Prism base')
    cpu=root/'ggml/src/ggml-cpu'
    p=cpu/'ggml-cpu.c';p.write_text(instrument_cpu(p.read_text(encoding='utf-8')),encoding='utf-8')
    replace_once(cpu/'quants.c','#include "build122_sampling.h"','#include "build122_sampling.h"\n#include "build123_unpack_reuse.h"')
    (cpu/'build123_unpack_reuse.h').write_text((Path(__file__).parent/'native/build123_unpack_reuse.h').read_text(encoding='utf-8'),encoding='utf-8')
    # The122 patch copies its header template, now including period0 and reuse TLS fields.
    replace_once(cpu/'build118_ptq1_cpu.h','return 8u | (BONSAI_CPU_NEON ? 16u : 0u);','return 32u | 8u | (BONSAI_CPU_NEON ? 16u : 0u);')
    ops=root/'ggml/src/ggml-metal/ggml-metal-ops.cpp'
    replace_once(ops,'if (flags < -1 || flags > 31 || (flags >= 0 && (flags & 24) == 24)) return 0;',
        'if (flags != 32 && (flags < -1 || flags > 31 || (flags >= 0 && (flags & 24) == 24))) return 0;')
    run_diff_check(root)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);apply(p.parse_args().root)
