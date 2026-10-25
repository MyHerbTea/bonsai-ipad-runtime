import os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))

class SDOTTests(unittest.TestCase):
    def source(self):
        native=Path(os.environ.get('BONSAI_PRISM_TEST_DIR','D:/codexSpace/iPad27B/native-prism'))
        source=(native/'ggml/src/ggml-cpu/quants.c').read_text(encoding='utf-8')
        return source

    def test_patch_retains_baseline_math_and_isolates_target(self):
        import rc126_build124_patch_sdot as patch
        source=self.source()
        # CI supplies the fully patched file; local snapshot has Build122.
        if 'BONSAI_SDOT_124' in source:
            a=source.index('// BONSAI_SDOT_124');b=source.index('// BONSAI_SDOT_124_END',a)+len('// BONSAI_SDOT_124_END\n');source=(source[:a]+source[b:]).replace(patch.ROUTE,'',1)
        result=patch.instrument_quants(source)
        a=source.index('void ggml_vec_dot_ptq1_0_q8_0_generic(')
        b=source.index('    static const uint8_t pow3[6]',a)
        end=source.index('\nvoid ',b)
        original=source[b:end]
        a=result.index('void ggml_vec_dot_ptq1_0_q8_0_generic(')
        b=result.index('    static const uint8_t pow3[6]',a)
        self.assertEqual(result[b:result.index('\nvoid ',b)],original)
        with self.assertRaises(ValueError):patch.instrument_quants(result)
        self.assertIn('target("dotprod")',result)
        self.assertEqual(result.count('vdotq_s32('),2)

    def test_assembly_gate_rejects_missing_sdot_and_hot_spills(self):
        from build124_inspect_assembly import inspect
        sample="""00000100 <_bonsai_sdot_ptq1_dot>:
 100: movi v0.4s, #0
 104: sdot v0.4s, v1.16b, v2.16b
 108: subs x0, x0, #1
 10c: b.ne 0x100
 110: ret
00000200 <_ggml_vec_dot_ptq1_0_q8_0>:
 200: smull v0.8h, v1.8b, v2.8b
 204: ret
"""
        self.assertEqual(inspect(sample)['candidate']['sdot'],1)
        apple=sample.replace('sdot v0.4s, v1.16b, v2.16b','sdot.4s v0, v1, v2')
        self.assertEqual(inspect(apple)['candidate']['sdot'],1)
        with self.assertRaises(ValueError):inspect(apple.replace('100: movi v0.4s, #0','100: st1.16b { v3 }, [sp]'))

        with self.assertRaises(ValueError):inspect(sample.replace('sdot','smull'))
        with self.assertRaises(ValueError):inspect(sample.replace('100: movi v0.4s, #0','100: str q3, [sp, #16]'))
        for store in ['str d3, [sp, #16]','stp d3, d4, [sp, #16]',
                      'stur s3, [x29, #-16]','st1 { v3.16b }, [sp]']:
            with self.subTest(store=store):
                with self.assertRaises(ValueError):inspect(sample.replace('100: movi v0.4s, #0','100: '+store))
        # Callee-save stores outside the repeated loop are permitted.
        save=sample.replace(' 100: movi',' fc: stp d8, d9, [sp, #32]\n 100: movi')
        self.assertEqual(inspect(save)['candidate']['hot_vector_spills'],[])

    def test_actual_native_control_capability_and_exclusive_flags(self):
        from test_build118_cpu import CPUPrefillTests
        CPUPrefillTests('test_actual_patched_native_strategy_control').test_actual_patched_native_strategy_control()

    def test_compiled_actual_arm64_parity_and_assembly(self):
        import rc126_build124_patch_sdot as patch
        if sys.platform!='darwin' or os.uname().machine!='arm64':
            self.skipTest('Apple ARM64 CI required; not a local parity PASS')
        import rc126_build118_patch_cpu_prefill as old
        source=self.source()
        if 'BONSAI_SDOT_124' not in source:source=patch.instrument_quants(source)
        a=source.index('// BONSAI_SDOT_124')
        b=source.index('\nvoid ',source.index('void ggml_vec_dot_ptq1_0_q8_0_generic(',a)+5)
        funcs=source[a:b]
        # Sampling clone is defined before the candidate region.
        sa=source.index('static void bonsai_sampled_ptq1_dot(')
        funcs=source[sa:a]+funcs
        preamble=r"""
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#define GGML_RESTRICT restrict
#define UNUSED(x) (void)(x)
#define QK_PTQ1_0 128
#define GGML_CPU_FP16_TO_FP32(x) ((float)(x))
typedef struct {uint8_t qs[24];uint8_t qh[2];_Float16 d;} block_ptq1_0;
typedef struct {_Float16 d;int8_t qs[32];} block_q8_0;
_Static_assert(sizeof(block_ptq1_0)==28,"PTQ1 layout");
_Static_assert(sizeof(block_q8_0)==34,"Q8 layout");
#include <sys/types.h>
#include <sys/sysctl.h>
static int probe_mode=-1;
static int probe_sysctl(const char *name,void *out,size_t *size,void *in,size_t in_size){
    if(probe_mode<0)return sysctlbyname(name,out,size,in,in_size);
    if(probe_mode==1)return -1;
    *(int *)out=probe_mode==0?0:1;
    if(probe_mode==2)*size=0;
    return 0;
}
#define sysctlbyname probe_sysctl
#include "build118_ptq1_cpu.h"
#undef sysctlbyname
#include "build122_sampling.h"
"""
        checks=r"""
static uint32_t rng=123;
static uint32_t next(void){rng=rng*1664525u+1013904223u;return rng;}
static _Float16 scale(void){uint16_t v=(uint16_t)(next()>>16);if((v&0x7c00)==0x7c00)v^=0x0400;_Float16 f;memcpy(&f,&v,2);return f;}
int main(void){
    assert(BonsaiNativeCPUCapabilities()&64u);
    for(probe_mode=0;probe_mode<3;probe_mode++){
        assert(!(BonsaiNativeCPUCapabilities()&64u));
        BonsaiNativeCPUConfigure(64);assert(atomic_load(&bonsai_cpu_flags)==-1);
    }
    probe_mode=-1;
    assert(BonsaiNativeCPUSamplingConfigure(0,0));
    for(int blocks=0;blocks<=9;blocks+=3)for(int byte=0;byte<256;byte++){
        block_ptq1_0 x[9];block_q8_0 y[36];
        for(int i=0;i<blocks;i++){
            x[i].d=scale();
            for(int j=0;j<24;j++)x[i].qs[j]=(uint8_t)(byte+j*13+i);
            for(int j=0;j<2;j++)x[i].qh[j]=(uint8_t)(byte+j*29+i);
            for(int k=0;k<4;k++){
                y[i*4+k].d=scale();
                for(int j=0;j<32;j++)y[i*4+k].qs[j]=j%3==0?-128:j%3==1?127:(int8_t)(next()>>24);
            }
        }
        float ref,actual;
        BonsaiNativeCPUConfigure(0);ggml_vec_dot_ptq1_0_q8_0_generic(blocks*128,&ref,0,x,0,y,0,1);
        BonsaiNativeCPUConfigure(64);ggml_vec_dot_ptq1_0_q8_0_generic(blocks*128,&actual,0,x,0,y,0,1);
        assert(memcmp(&ref,&actual,4)==0);
    }
    assert(BonsaiNativeCPUCounter(0)==0 && BonsaiNativeCPUCounter(1)==0 && BonsaiNativeCPUCounter(2)==0);
    BonsaiNativeCPUConfigure(-1);
    puts("SDOT actual baseline parity, signed extremes, packed bytes, finite half scales, zero/multiple blocks: PASS");
}
"""
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            for name in ['build118_ptq1_cpu.h','build122_sampling.h','build124_sdot.h']:
                # Header118 in the patched native tree includes hardware admission.
                native=Path(os.environ['BONSAI_PRISM_TEST_DIR'])/'ggml/src/ggml-cpu'/name
                shutil.copy(native,folder)
            (folder/'build118_ptq1_lut.inc').write_text(old.lookup_table())
            (folder/'check.c').write_text(preamble+funcs+checks)
            for contract in ['off','on']:
                command=['xcrun','clang','-std=c11','-O3','-ffp-contract='+contract]
                cp=subprocess.run(command+['-fsanitize=address,undefined',str(folder/'check.c'),'-o',str(folder/'check')],capture_output=True,text=True)
                self.assertEqual(cp.returncode,0,cp.stderr[-6000:])
                result=subprocess.run([str(folder/'check')],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr[-6000:]);self.assertIn('PASS',result.stdout)
            output=ROOT/'build/sdot-analysis';output.mkdir(parents=True,exist_ok=True)
            cp=subprocess.run(['xcrun','--sdk','iphoneos','clang','-target','arm64-apple-ios15.0','-std=c11','-O3','-S',str(folder/'check.c'),'-o',str(output/'fixture-ios.s')],capture_output=True,text=True)
            self.assertEqual(cp.returncode,0,cp.stderr[-6000:])
            assembly=(output/'fixture-ios.s').read_text()
            self.assertIn('sdot',assembly.lower())

if __name__=='__main__':unittest.main()
