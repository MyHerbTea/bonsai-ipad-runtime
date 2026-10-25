"""Execute the real pinned CPU chunk and kernels on Apple ARM64, never synthetic device timings."""
import ast,os,shutil,subprocess,tempfile
from pathlib import Path


def verify(root,native):
    old=ast.parse((root/'tools/tests/test_build123_unpack_reuse.py').read_text(encoding='utf-8'))
    method=next(x for x in ast.walk(old) if isinstance(x,ast.FunctionDef) and x.name=='test_compiled_actual_chunk_float_parity_strides_broadcast_and_reuse')
    expr=next(x.value for x in method.body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='program' for t in x.targets))
    q=(native/'ggml/src/ggml-cpu/quants.c').read_text(encoding='utf-8')
    start=q.index('static void bonsai_sampled_ptq1_dot(')
    end=q.index('\nvoid ',q.index('void ggml_vec_dot_ptq1_0_q8_0_generic(',start)+5)
    generic=q[start:end]
    c=(native/'ggml/src/ggml-cpu/ggml-cpu.c').read_text(encoding='utf-8')
    def chunk(s):
        a=s.index('static void ggml_compute_forward_mul_mat_one_chunk(')
        return s[a:s.index('\nvoid ggml_compute_forward_mul_mat(',a)]
    raw=subprocess.check_output(['git','-C',str(native),'show','HEAD:ggml/src/ggml-cpu/ggml-cpu.c'],text=True)
    original=chunk(raw).replace('ggml_compute_forward_mul_mat_one_chunk','reference_chunk')
    changed=chunk(c)
    program=eval(compile(ast.Expression(expr),'<actual Build123 fixture template>','eval'),{'generic':generic,'original':original,'changed':changed})
    program=program.replace('#include "build118_ptq1_cpu.h"',r'''#include <sys/types.h>
#include <sys/sysctl.h>
static int probe_unavailable=0;
static int pair_probe_sysctl(const char *n,void *out,size_t *size,void *in,size_t insize) {
    if(probe_unavailable)return -1;
    return sysctlbyname(n,out,size,in,insize);
}
#define sysctlbyname pair_probe_sysctl
#include "build118_ptq1_cpu.h"
#undef sysctlbyname
''',1)
    program=program.replace('BonsaiNativeCPUConfigure(32)','BonsaiNativeCPUConfigure(128)')
    a=program.index('    if(end-begin>=2) {')
    b=program.index('    // Cross-broadcast',a)
    program=program[:a]+'''    if(cols>1 && cols<=8 && (rows/2>=2 || rows-rows/2>=2)) {
        assert(BonsaiNativeCPUSamplingCounter(16)>0);
        assert(BonsaiNativeCPUSamplingCounter(17)>0);
    } else assert(BonsaiNativeCPUSamplingCounter(16)==0 && BonsaiNativeCPUSamplingCounter(17)==0);
''' +program[b:]
    program=program.replace('for(int cols=1;cols<=8;cols++)','for(int cols=1;cols<=9;cols++)')
    program=program.replace('for(int rows=1;rows<=17;rows+=16)','for(int rows=1;rows<=33;rows++)')
    a=program.index('int main(void) {')
    program=program[:a]+r'''
static void direct_pair(void) {
    assert(BonsaiNativeCPUCapabilities()&128u);
    probe_unavailable=1;
    assert(!(BonsaiNativeCPUCapabilities()&128u));
    BonsaiNativeCPUConfigure(128);assert(atomic_load(&bonsai_cpu_flags)==-1);
    assert(!BonsaiNativeCPUSDOTPairEnabled());
    probe_unavailable=0;
    BonsaiNativeCPUConfigure(128);
    assert(BonsaiNativeCPUSamplingConfigure(1,0));assert(!BonsaiNativeCPUSDOTPairEnabled());
    assert(BonsaiNativeCPUSamplingConfigure(0,1000));assert(!BonsaiNativeCPUSDOTPairEnabled());
    assert(BonsaiNativeCPUSamplingConfigure(0,0));assert(BonsaiNativeCPUSDOTPairEnabled());
    for(int blocks=0;blocks<=7;blocks++)for(int byte=0;byte<256;byte++) {
        block_ptq1_0 x0[7],x1[7];block_q8_0 y[28];
        for(int i=0;i<blocks;i++) {
            x0[i].d=scale();x1[i].d=scale();
            for(int j=0;j<24;j++){x0[i].qs[j]=(uint8_t)(byte+j*13+i);x1[i].qs[j]=(uint8_t)(255-byte+j*29+i);}
            for(int j=0;j<2;j++){x0[i].qh[j]=(uint8_t)(byte+j*31);x1[i].qh[j]=(uint8_t)(byte+j*7);}
            for(int k=0;k<4;k++) {
                y[i*4+k].d=scale();
                for(int j=0;j<32;j++)y[i*4+k].qs[j]=j%3==0?-128:j%3==1?127:(int8_t)(next()>>24);
            }
        }
        float a0,a1,b0,b1,c0,c1;
        BonsaiNativeCPUConfigure(0);
        ggml_vec_dot_ptq1_0_q8_0_generic(blocks*128,&a0,0,x0,0,y,0,1);
        ggml_vec_dot_ptq1_0_q8_0_generic(blocks*128,&a1,0,x1,0,y,0,1);
        BonsaiNativeCPUConfigure(64);
        ggml_vec_dot_ptq1_0_q8_0_generic(blocks*128,&b0,0,x0,0,y,0,1);
        ggml_vec_dot_ptq1_0_q8_0_generic(blocks*128,&b1,0,x1,0,y,0,1);
        BonsaiNativeCPUConfigure(128);
        assert(BonsaiNativeCPUSDOTPair(blocks*128,&c0,&c1,x0,x1,y));
        assert(!memcmp(&a0,&b0,4) && !memcmp(&a0,&c0,4));
        assert(!memcmp(&a1,&b1,4) && !memcmp(&a1,&c1,4));
    }
}
''' +program[a:]
    program=program.replace('int main(void) {','int main(void) {\n    direct_pair();',1)
    program=program.replace('puts("flag17 actual pinned chunk parity, strided/converted Q8, broadcast, partial/empty ranges, reuse proof and off counters: PASS");','puts("Build125 actual pair/chunk bitwise parity, all bytes, signed extremes, finite half, rows1..33, odd tails, strided/converted Q8, broadcast/empty ranges and guards: PASS");')
    output=root/'build/pair-analysis';output.mkdir(parents=True,exist_ok=True)
    (output/'actual-pair-fixture.c').write_text(program,encoding='utf-8')
    import rc126_build118_patch_cpu_prefill as p118
    with tempfile.TemporaryDirectory() as folder:
        folder=Path(folder)
        for name in ['build118_ptq1_cpu.h','build122_sampling.h','build123_unpack_reuse.h','build124_sdot.h']:
            shutil.copy(native/'ggml/src/ggml-cpu'/name,folder)
        (folder/'build118_ptq1_lut.inc').write_text(p118.lookup_table(),encoding='utf-8')
        src=folder/'check.c';src.write_text(program,encoding='utf-8')
        for contraction in ['off','on']:
            command=['xcrun','clang','-std=c11','-O3','-ffp-contract='+contraction,'-fsanitize=address,undefined','-fno-sanitize-recover=all',str(src),'-o',str(folder/'check')]
            cp=subprocess.run(command,capture_output=True,text=True)
            if cp.returncode:raise AssertionError(cp.stderr[-10000:])
            cp=subprocess.run([str(folder/'check')],capture_output=True,text=True,timeout=180)
            (output/('sanitizers-'+contraction+'.txt')).write_text(cp.stdout+cp.stderr,encoding='utf-8')
            if cp.returncode:raise AssertionError(cp.stderr[-10000:])
            assert 'Build125 actual pair/chunk bitwise parity' in cp.stdout
        cp=subprocess.run(['xcrun','--sdk','iphoneos','clang','-target','arm64-apple-ios15.0','-std=c11','-O3','-c',str(src),'-o',str(folder/'fixture.o')],capture_output=True,text=True)
        if cp.returncode:raise AssertionError(cp.stderr[-10000:])
        assembly=subprocess.check_output(['xcrun','llvm-objdump','--disassemble','--no-show-raw-insn',str(folder/'fixture.o')],text=True)
        (output/'fixture-disassembly.txt').write_text(assembly,encoding='utf-8')
        from build125_inspect_assembly import inspect
        import json
        (output/'fixture-inspection.json').write_text(json.dumps(inspect(assembly),indent=2)+'\n',encoding='utf-8')
