import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import rc126_build118_patch_cpu_prefill as patch


class CPUPrefillTests(unittest.TestCase):
    def test_actual_patched_native_strategy_control(self):
        compiler=shutil.which('clang++') or shutil.which('c++') or shutil.which('g++')
        if not compiler:self.skipTest('C++ compiler absent; Apple CI executes patched strategy control')
        native=os.environ.get('BONSAI_PRISM_TEST_DIR')
        if not native:self.skipTest('set BONSAI_PRISM_TEST_DIR after full patch chain')
        code=(Path(native)/'ggml/src/ggml-metal/ggml-metal-ops.cpp').read_text()
        control=code[code.index('// BONSAI_PTQ1_BENCHMARK_114.'):code.index('static inline void bonsai_m5_ptq1_tensor_trace')]
        preamble=r'''
#include <atomic>
#include <chrono>
#include <thread>
#include <cstdint>
#include <cassert>
#include <initializer_list>
enum {GGML_TYPE_PTQ1_0, GGML_TYPE_F32};
struct ggml_tensor {int type;int64_t ne[4];uint64_t nb[4];ggml_tensor *src[2];};
bool ggml_is_transposed(const ggml_tensor *) {return false;}
std::atomic<uint64_t> bonsai_ptq1_route_selected_count{0},bonsai_ptq1_pipeline_ready_count{0},bonsai_ptq1_dispatch_enqueued_count{0},bonsai_ptq1_fallback_count{0};
uint32_t cpu_caps=24;int cpu_flags=-1,resets=0;
extern "C" uint32_t BonsaiNativeCPUCapabilities(void) {return cpu_caps;}
extern "C" void BonsaiNativeCPUConfigure(int flags) {cpu_flags=flags;}
extern "C" void BonsaiNativeCPUBeginRequest(void) {resets++;}
'''
        checks=r'''
int main() {
    BonsaiNativeBenchmarkPublishCapabilities(7);
    assert(BonsaiNativeBenchmarkCapabilities()==31);
    for(int flag: {0,4,8,16,12,20}) {
        assert(BonsaiNativeBenchmarkConfigure(flag)==1);assert(cpu_flags==flag);
    }
    int previous=cpu_flags;
    for(int flag: {-2,24,25,31,32}) {
        assert(BonsaiNativeBenchmarkConfigure(flag)==0);assert(cpu_flags==previous);
    }
    cpu_caps=8;assert(BonsaiNativeBenchmarkConfigure(16)==0);
    assert(BonsaiNativeBenchmarkConfigure(8)==1 && cpu_flags==8);
    BonsaiNativeBenchmarkIncrement(6);
    assert(BonsaiNativeBenchmarkConfigure(0)==0 && cpu_flags==8);
    BonsaiNativeBenchmarkIncrement(7);
    assert(BonsaiNativeBenchmarkConfigure(-1)==1 && cpu_flags==-1);
    BonsaiNativeBenchmarkBeginRequest();assert(resets==1);
}
'''
        if 'flags != 32' in control:
            checks=checks.replace('    int previous=cpu_flags;','''    cpu_caps=56;assert(BonsaiNativeBenchmarkCapabilities()==63);
    assert(BonsaiNativeBenchmarkConfigure(32)==1 && cpu_flags==32);
    assert(BonsaiNativeBenchmarkConfigure(33)==0 && cpu_flags==32);
    cpu_caps=24;assert(BonsaiNativeBenchmarkConfigure(0)==1);
    int previous=cpu_flags;''')
        if 'flags != 64' in control:
            checks=checks.replace('    int previous=cpu_flags;','''    cpu_caps=120;assert(BonsaiNativeBenchmarkCapabilities()==127);
    assert(BonsaiNativeBenchmarkConfigure(64)==1 && cpu_flags==64);
    for(int flag: {65,68,80,96,127})assert(BonsaiNativeBenchmarkConfigure(flag)==0 && cpu_flags==64);
    cpu_caps=56;assert(BonsaiNativeBenchmarkConfigure(64)==0 && cpu_flags==64);
    cpu_caps=24;assert(BonsaiNativeBenchmarkConfigure(0)==1);
    int previous=cpu_flags;''')
        if 'flags != 128' in control:
            checks=checks.replace('    int previous=cpu_flags;','''    cpu_caps=248;assert(BonsaiNativeBenchmarkCapabilities()==255);
    assert(BonsaiNativeBenchmarkConfigure(128)==1 && cpu_flags==128);
    for(int flag:{129,160,192,255})assert(BonsaiNativeBenchmarkConfigure(flag)==0 && cpu_flags==128);
    cpu_caps=120;assert(BonsaiNativeBenchmarkConfigure(128)==0 && cpu_flags==128);
    cpu_caps=24;assert(BonsaiNativeBenchmarkConfigure(0)==1);
    int previous=cpu_flags;''')
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);source=folder/'control.cpp';binary=folder/('control.exe' if os.name=='nt' else 'control')
            source.write_text(preamble+control+checks)
            subprocess.run([compiler,'-std=c++17','-pthread',str(source),'-o',str(binary)],check=True,capture_output=True)
            subprocess.run([str(binary)],check=True,capture_output=True)

    def test_all_bytes_lookup_format(self):
        table=patch.lookup_table().splitlines()
        self.assertEqual(len(table),256)
        for byte,row in enumerate(table):
            actual=[int(x) for x in row.strip('{},').split(',')]
            expected=[]
            for power in (1,3,9,27,81):
                wrapped=(byte*power)%256
                expected.append((wrapped*3//256)-1)
            self.assertEqual(actual,expected)

    def test_actual_compiled_scalar_lookup_and_neon_parity(self):
        compiler=shutil.which('clang') or shutil.which('cc') or shutil.which('gcc')
        if not compiler:self.skipTest('C compiler absent; Apple CI executes actual arm64 C/NEON')
        native=os.environ.get('BONSAI_PRISM_TEST_DIR')
        if not native:self.skipTest('set BONSAI_PRISM_TEST_DIR after full patch chain')
        source=(Path(native)/'ggml/src/ggml-cpu/quants.c').read_text()
        start=source.index('void ggml_vec_dot_ptq1_0_q8_0_generic(')
        end=source.index('\nvoid ',start+5)
        function=source[start:end]
        sampling='BONSAI_SAMPLING_122' in source
        if sampling:
            function='#include \"build122_sampling.h\"\n'+source[source.index('static void bonsai_sampled_ptq1_dot('):start]+function
        program=r'''
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#define GGML_RESTRICT restrict
#define UNUSED(x) (void)(x)
#define QK_PTQ1_0 128
#define GGML_CPU_FP16_TO_FP32(x) (x)
typedef struct {float d; uint8_t qs[24]; uint8_t qh[2];} block_ptq1_0;
typedef struct {float d; int8_t qs[32];} block_q8_0;
#include "build118_ptq1_cpu.h"
''' + function + r'''
static uint32_t state=118;
static uint32_t next(void) { state=state*1664525u+1013904223u; return state; }
int main(void) {
    if (getenv("BONSAI_REQUIRE_NEON")) assert(BONSAI_CPU_NEON);
    for(int byte=0;byte<256;byte++) {
        block_ptq1_0 x={0}; int8_t a[128],b[128];
        memset(x.qs,byte,24);memset(x.qh,byte,2);
        bonsai_cpu_decode(&x,a,0);bonsai_cpu_decode(&x,b,1);
        assert(memcmp(a,b,128)==0);
        int offset=0; const int sizes[2]={16,8};
        for(int st=0;st<2;st++)for(int digit=0,factor=1;digit<5;digit++,factor*=3)
            for(int m=0;m<sizes[st];m++) assert(a[offset++]==((uint8_t)(byte*factor)*3>>8)-1);
        for(int digit=0,factor=1;digit<4;digit++,factor*=3)
            for(int m=0;m<2;m++)assert(a[offset++]==((uint8_t)(byte*factor)*3>>8)-1);
        assert(offset==128);
    }
    for(int trial=0;trial<1000;trial++) {
        block_ptq1_0 x[7];block_q8_0 y[28];int blocks=1+trial%7;
        for(int i=0;i<blocks;i++) {
            x[i].d=(int)(next()%17)*0.125f;
            for(int j=0;j<24;j++)x[i].qs[j]=(uint8_t)(next()>>24);
            for(int j=0;j<2;j++)x[i].qh[j]=(uint8_t)(next()>>24);
            for(int k=0;k<4;k++) {
                y[i*4+k].d=(int)(next()%17)*0.125f;
                for(int j=0;j<32;j++)y[i*4+k].qs[j]=trial%3==0?-128:trial%3==1?127:(int8_t)(next()>>24);
            }
        }
        float baseline=0,lookup=0,neon=0;
        BonsaiNativeCPUConfigure(0);ggml_vec_dot_ptq1_0_q8_0_generic(blocks*128,&baseline,0,x,0,y,0,1);
        BonsaiNativeCPUConfigure(8);ggml_vec_dot_ptq1_0_q8_0_generic(blocks*128,&lookup,0,x,0,y,0,1);
        assert(memcmp(&baseline,&lookup,sizeof(float))==0);
#ifdef BONSAI_SAMPLING_TEST
        float sampled;bonsai_sampled_ptq1_dot(blocks*128,&sampled,0,x,0,y,0,1);
        assert(memcmp(&baseline,&sampled,sizeof(float))==0);
#endif
#if BONSAI_CPU_NEON
        assert(BonsaiNativeCPUCapabilities()&16);
        BonsaiNativeCPUConfigure(16);ggml_vec_dot_ptq1_0_q8_0_generic(blocks*128,&neon,0,x,0,y,0,1);
        assert(memcmp(&baseline,&neon,sizeof(float))==0);
#else
        assert(!(BonsaiNativeCPUCapabilities()&16));(void)neon;
#endif
    }
    assert(BonsaiNativeCPUCounter(0)==1000 && BonsaiNativeCPUCounter(1)==1000);
    BonsaiNativeCPUBeginRequest();assert(BonsaiNativeCPUCounter(0)==0);
    BonsaiNativeCPUConfigure(-1);
    block_ptq1_0 x={0};block_q8_0 y[4]={{0}};float result;
    ggml_vec_dot_ptq1_0_q8_0_generic(128,&result,0,&x,0,y,0,1);
    assert(BonsaiNativeCPUCounter(0)==0);
    assert(BonsaiNativeCPUCounter(-1)==0 && BonsaiNativeCPUCounter(3)==0);
#ifdef BONSAI_SAMPLING_TEST
    for(int on=0;on<=1;on++) {
        assert(BonsaiNativeCPUSamplingConfigure(on,10000)==1);
        BonsaiNativeCPUBeginRequest();BonsaiNativeCPUConfigure(0);BonsaiNativeCPUSamplingPhase(1);
        for(int worker=0;worker<6;worker++) {
            BonsaiNativeCPUSamplingEnter(worker);
            for(int call=0;call<20000;call++)ggml_vec_dot_ptq1_0_q8_0_generic(128,&result,0,&x,0,y,0,1);
            BonsaiNativeCPUSamplingLeave();
        }
        BonsaiNativeCPUSamplingPhase(0);
        assert(BonsaiNativeCPUCounter(0)==(on?120000:0));
        assert(BonsaiNativeCPUSamplingCounter(0)==120000);
        assert(BonsaiNativeCPUSamplingCounter(1)==12);
        assert(BonsaiNativeCPUSamplingCounter(3)==12);
        assert(BonsaiNativeCPUSamplingCounter(8)==(uint64_t)on);
        assert(BonsaiNativeCPUSamplingCounter(10)==6);
        assert(BonsaiNativeCPUSamplingCounter(11)==2);
        assert(BonsaiNativeCPUSamplingConfigure(2,10000)==0);
    }
    assert(BonsaiNativeCPUSamplingConfigure(1,10000)==1);
    BonsaiNativeCPUSamplingEnter(0);
    ggml_vec_dot_ptq1_0_q8_0_generic(128,&result,0,&x,0,y,0,1);
    BonsaiNativeCPUSamplingLeave();assert(BonsaiNativeCPUSamplingCounter(0)==0);
#endif
    puts("Build118 actual scalar/LUT/ARM-NEON integer and float parity, bounds and disable: PASS");
}
'''
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            shutil.copy(ROOT/'tools/native/build118_ptq1_cpu.h',folder)
            if sampling:shutil.copy(ROOT/'tools/native/build122_sampling.h',folder)
            (folder/'build118_ptq1_lut.inc').write_text(patch.lookup_table())
            if sampling:program='#define BONSAI_SAMPLING_TEST 1\n'+program
            (folder/'check.c').write_text(program)
            binary=folder/('check.exe' if os.name=='nt' else 'check')
            subprocess.run([compiler,'-std=c11','-O2','-ffp-contract=off','-fsanitize=address,undefined',str(folder/'check.c'),'-o',str(binary)],check=True,capture_output=True)
            result=subprocess.run([str(binary)],check=True,capture_output=True,text=True)
            self.assertIn('PASS',result.stdout)

if __name__=='__main__':unittest.main()
