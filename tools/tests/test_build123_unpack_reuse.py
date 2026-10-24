import importlib.util,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))

class UnpackReuseTests(unittest.TestCase):
    def test_compiled_actual_chunk_float_parity_strides_broadcast_and_reuse(self):
        compiler=shutil.which('clang')
        if not compiler or os.name=='nt':self.skipTest('Apple CI executes actual C/arm64 parity and sanitizers')
        import rc126_build123_patch_unpack_reuse as patch
        import rc126_build118_patch_cpu_prefill as old
        native=Path(os.environ['BONSAI_PRISM_TEST_DIR'])
        def raw(file):return subprocess.check_output(['git','-C',str(native),'show','HEAD:ggml/src/ggml-cpu/'+file],text=True)
        q=raw('quants.c');a=q.index('void ggml_vec_dot_ptq1_0_q8_0_generic(');b=q.index('\nvoid ',a+5);generic=q[a:b]
        s=raw('ggml-cpu.c');a=s.index('static void ggml_compute_forward_mul_mat_one_chunk(');b=s.index('\nstatic void ggml_compute_forward_mul_mat(',a)
        original=s[a:b].replace('ggml_compute_forward_mul_mat_one_chunk','reference_chunk')
        changed=patch.instrument_cpu(s);a=changed.index('static void ggml_compute_forward_mul_mat_one_chunk(');b=changed.index('\nstatic void ggml_compute_forward_mul_mat(',a)
        program=r'''
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <limits.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#define GGML_RESTRICT restrict
#define GGML_UNUSED(x) (void)(x)
#define UNUSED(x) (void)(x)
#define MIN(a,b) ((a)<(b)?(a):(b))
#define QK_PTQ1_0 128
#define GGML_CPU_FP16_TO_FP32(x) ((float)(x))
typedef struct {uint8_t qs[24];uint8_t qh[2];_Float16 d;} block_ptq1_0;
typedef struct {_Float16 d;int8_t qs[32];} block_q8_0;
_Static_assert(sizeof(block_ptq1_0)==28,"actual PTQ1 block layout");
_Static_assert(sizeof(block_q8_0)==34,"actual Q8 block layout");
#include "build118_ptq1_cpu.h"
#include "build122_sampling.h"
#include "build123_unpack_reuse.h"
''' + generic + r'''
enum ggml_type {GGML_TYPE_F32,GGML_TYPE_Q8_0,GGML_TYPE_PTQ1_0};
struct ggml_tensor {enum ggml_type type;int64_t ne[4];size_t nb[4];void *data;struct ggml_tensor *src[2];};
struct ggml_compute_params {void *wdata;};
typedef void(*ggml_vec_dot_t)(int,float*,size_t,const void*,size_t,const void*,size_t,int);
static ggml_vec_dot_t ggml_cpu_vec_dot(const struct ggml_tensor*x){(void)x;return ggml_vec_dot_ptq1_0_q8_0_generic;}
static enum ggml_type ggml_cpu_vec_dot_type(const struct ggml_tensor*x){(void)x;return GGML_TYPE_Q8_0;}
static size_t ggml_type_size(enum ggml_type t){return t==GGML_TYPE_PTQ1_0?sizeof(block_ptq1_0):t==GGML_TYPE_Q8_0?sizeof(block_q8_0):4;}
static size_t ggml_row_size(enum ggml_type t,int64_t n){return t==GGML_TYPE_PTQ1_0?n/128*sizeof(block_ptq1_0):t==GGML_TYPE_Q8_0?n/32*sizeof(block_q8_0):n*4;}
static int ggml_is_contiguous(const struct ggml_tensor*t){return t->nb[1]==ggml_row_size(t->type,t->ne[0]);}
#define GGML_TENSOR_BINARY_OP_LOCALS \
 const int64_t ne00=src0->ne[0],ne02=src0->ne[2],ne03=src0->ne[3],ne10=src1->ne[0],ne11=src1->ne[1],ne12=src1->ne[2],ne13=src1->ne[3],ne1=dst->ne[1]; \
 const size_t nb00=src0->nb[0],nb01=src0->nb[1],nb02=src0->nb[2],nb03=src0->nb[3],nb11=src1->nb[1],nb12=src1->nb[2],nb13=src1->nb[3],nb0=dst->nb[0],nb1=dst->nb[1],nb2=dst->nb[2],nb3=dst->nb[3];
''' + original + changed[a:b] + r'''
static uint32_t rng=123;
static uint32_t next(void){rng=rng*1664525u+1013904223u;return rng;}
static _Float16 scale(void) {
    uint16_t bits=(uint16_t)(next()>>16);
    if((bits&0x7c00)==0x7c00)bits^=0x0400; // finite half, varied signs/exponents/mantissas/subnormals
    _Float16 value;memcpy(&value,&bits,2);return value;
}
static void check(int blocks,int rows,int cols,int mode,int partial) {
    const int total=cols*4,rb=blocks+1,yb=blocks*4+(mode==1?1:0),stride=rows+3;
    const int w2=mode>0?2:1,w3=mode==2?2:1;
    block_ptq1_0 *x=calloc((size_t)rows*rb*w2*w3,sizeof(*x));
    block_q8_0 *y=calloc((size_t)total*yb,sizeof(*y));
    float *ref=malloc((size_t)stride*total*sizeof(float)),*actual=malloc((size_t)stride*total*sizeof(float));
    assert(x&&y&&ref&&actual);
    for(int i=0;i<rows*rb*w2*w3;i++) {
        x[i].d=scale();
        for(int j=0;j<24;j++)x[i].qs[j]=(uint8_t)(next()>>24);
        for(int j=0;j<2;j++)x[i].qh[j]=(uint8_t)(next()>>24);
    }
    for(int i=0;i<total*yb;i++) {
        y[i].d=scale();
        for(int j=0;j<32;j++)y[i].qs[j]=j%3==0?-128:j%3==1?127:(int8_t)(next()>>24);
    }
    for(int i=0;i<stride*total;i++)ref[i]=actual[i]=-9999.f;
    struct ggml_tensor w={.type=GGML_TYPE_PTQ1_0,.ne={blocks*128,rows,w2,w3},.nb={sizeof(*x),rb*sizeof(*x),rows*rb*sizeof(*x),w2*rows*rb*sizeof(*x)},.data=x};
    struct ggml_tensor in={.type=mode==2?GGML_TYPE_F32:GGML_TYPE_Q8_0,.ne={blocks*128,cols,2,2},.nb={sizeof(*y),yb*sizeof(*y),cols*yb*sizeof(*y),2*cols*yb*sizeof(*y)},.data=y};
    if(mode==2){in.nb[0]=4;in.nb[1]=blocks*128*4;in.nb[2]=cols*in.nb[1];in.nb[3]=2*in.nb[2];}
    struct ggml_tensor dst={.type=GGML_TYPE_F32,.ne={rows,cols,2,2},.nb={4,stride*4,cols*stride*4,2*cols*stride*4},.data=ref,.src={&w,&in}};
    struct ggml_compute_params params={.wdata=y};
    const int begin=partial&&cols>=4?1:0,end=partial&&cols>=4?cols-1:cols;
    BonsaiNativeCPUConfigure(0);assert(BonsaiNativeCPUSamplingConfigure(0,0)==1);
    for(int group=0;group<4;group++)reference_chunk(&params,&dst,GGML_TYPE_PTQ1_0,1,0,rows,group*cols+begin,group*cols+end);
    dst.data=actual;BonsaiNativeCPUConfigure(32);
    BonsaiNativeCPUSamplingPhase(1);BonsaiNativeCPUSamplingEnter(0);
    for(int group=0;group<4;group++) {
        // Split row ownership, including an empty range for rows1.
        ggml_compute_forward_mul_mat_one_chunk(&params,&dst,GGML_TYPE_PTQ1_0,1,0,rows/2,group*cols+begin,group*cols+end);
        ggml_compute_forward_mul_mat_one_chunk(&params,&dst,GGML_TYPE_PTQ1_0,1,rows/2,rows,group*cols+begin,group*cols+end);
    }
    BonsaiNativeCPUSamplingLeave();BonsaiNativeCPUSamplingPhase(0);
    assert(memcmp(ref,actual,(size_t)stride*total*sizeof(float))==0);
    assert(BonsaiNativeCPUCounter(0)==0 && BonsaiNativeCPUSamplingCounter(0)==0);
    if(end-begin>=2) {
        assert(BonsaiNativeCPUSamplingCounter(13)==(uint64_t)rows*4);
        assert(BonsaiNativeCPUSamplingCounter(14)==(uint64_t)rows*4*blocks);
        assert(BonsaiNativeCPUSamplingCounter(15)==(uint64_t)rows*4*(end-begin));
    } else assert(BonsaiNativeCPUSamplingCounter(13)==0);
    // Cross-broadcast ranges must remain correct through the original fallback.
    for(int i=0;i<stride*total;i++)ref[i]=actual[i]=-9999.f;
    dst.data=ref;reference_chunk(&params,&dst,GGML_TYPE_PTQ1_0,1,0,rows,0,total);
    dst.data=actual;ggml_compute_forward_mul_mat_one_chunk(&params,&dst,GGML_TYPE_PTQ1_0,1,0,rows,0,total);
    assert(memcmp(ref,actual,(size_t)stride*total*sizeof(float))==0);
    BonsaiNativeCPUConfigure(-1);assert(!BonsaiNativeCPUReuseEnabled());
    free(x);free(y);free(ref);free(actual);
}
int main(void) {
    for(int blocks=1;blocks<=7;blocks+=3)for(int rows=1;rows<=17;rows+=16)
        for(int cols=1;cols<=8;cols++)for(int mode=0;mode<3;mode++)for(int partial=0;partial<2;partial++)
            check(blocks,rows,cols,mode,partial);
    puts("flag17 actual pinned chunk parity, strided/converted Q8, broadcast, partial/empty ranges, reuse proof and off counters: PASS");
}
'''
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            for h in ['build118_ptq1_cpu.h','build122_sampling.h','build123_unpack_reuse.h']:shutil.copy(ROOT/'tools/native'/h,folder)
            (folder/'build118_ptq1_lut.inc').write_text(old.lookup_table())
            (folder/'check.c').write_text(program);binary=folder/'check'
            for contract in ['off','on']:
                cp=subprocess.run([compiler,'-std=c11','-O2','-ffp-contract='+contract,'-fsanitize=address,undefined',str(folder/'check.c'),'-o',str(binary)],capture_output=True,text=True)
                self.assertEqual(cp.returncode,0,cp.stderr[-6000:])
                result=subprocess.run([str(binary)],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr[-6000:]);self.assertIn('PASS',result.stdout)

    def test_cpu_route_preserves_fallback_and_barriers(self):
        path=ROOT/'tools/rc126_build123_patch_unpack_reuse.py'
        self.assertTrue(path.exists(),'flag17 implementation missing')
        spec=importlib.util.spec_from_file_location('reuse',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        native=Path(os.environ.get('BONSAI_PRISM_TEST_DIR','D:/codexSpace/iPad27B/native-prism'))
        if not native.exists():self.skipTest('pinned native required')
        raw=subprocess.check_output(['git','-C',str(native),'show','HEAD:ggml/src/ggml-cpu/ggml-cpu.c'],text=True,encoding='utf-8')
        result=m.instrument_cpu(raw)
        self.assertEqual(result.count('ggml_barrier('),raw.count('ggml_barrier('))
        self.assertIn('BonsaiNativeCPUReuseRow',result)
        self.assertIn('columns >= 2 && columns <= 8',result)
        self.assertIn('vec_dot(ne00, &tmp[ir0 - iir0]',result)
        with self.assertRaises(ValueError):m.instrument_cpu(result)

if __name__=='__main__':unittest.main()
