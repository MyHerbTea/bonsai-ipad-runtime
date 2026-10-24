"""Timing only, applied after existing patches to the pinned CPU graph executor."""
from pathlib import Path
import argparse
from rc126_build113_patch_prism_ptq1_tensorops import BASE_SHA, run_git, replace_once, run_diff_check


def instrument(source):
    if 'BONSAI_CPU_TIMING_121' in source:
        raise ValueError('Build121 timing already applied')
    start = source.index('static thread_ret_t ggml_graph_compute_thread(void * data) {')
    end = source.index('\n#ifndef GGML_USE_OPENMP', source.index('\n    return 0;\n}', start))
    body = source[start:end]
    anchor = '    for (int node_n = 0; node_n < cgraph->n_nodes'
    body = body.replace(anchor, '    // BONSAI_CPU_TIMING_121: no added barriers or worker-time summation.\n    uint64_t bonsai_timing_start = 0;\n    int bonsai_timing_category = -1;\n\n'+anchor, 1)
    anchor = '        // TODO: move fused-op detection'
    inserted = '''        if (state->ith == 0) {
            bonsai_timing_category = 3;
            if (node->op == GGML_OP_MUL_MAT || node->op == GGML_OP_MUL_MAT_ID) {
                bonsai_timing_category = 2;
                if (node->op == GGML_OP_MUL_MAT &&
                    ggml_get_op_params_i32(node,1) == GGML_HINT_SRC0_IS_HADAMARD && !params.use_ref)
                    bonsai_timing_category = 1;
                else if (node->src[0] && node->src[0]->type == GGML_TYPE_PTQ1_0)
                    bonsai_timing_category = 0;
            }
            bonsai_timing_start = bonsai_cpu_time_begin();
        }

'''
    assert anchor in body
    body = body.replace(anchor, inserted+anchor, 1)
    anchor = '''        if (node_n + 1 < cgraph->n_nodes) {
            ggml_barrier(state->threadpool);
        }'''
    replacement = '''        if (node_n + 1 < cgraph->n_nodes) {
            ggml_barrier(state->threadpool);
            if (state->ith == 0) {
                bonsai_cpu_time_end(bonsai_timing_category, bonsai_timing_start);
                bonsai_timing_start = 0;
            }
        }'''
    assert anchor in body
    body = body.replace(anchor, replacement, 1)
    anchor = '    ggml_barrier(state->threadpool);\n\n#ifdef GGML_USE_CPU_RISCV64_SPACEMIT'
    replacement = '''    ggml_barrier(state->threadpool);
    if (state->ith == 0) {
        bonsai_cpu_time_end(bonsai_timing_category, bonsai_timing_start);
    }

#ifdef GGML_USE_CPU_RISCV64_SPACEMIT'''
    assert anchor in body
    body = body.replace(anchor,replacement,1)
    return source[:start]+body+source[end:]


def apply(root):
    if run_git(root,'rev-parse','HEAD') != BASE_SHA:
        raise ValueError('wrong Prism base')
    cpu=root/'ggml/src/ggml-cpu'
    target=cpu/'ggml-cpu.c'
    source=target.read_text(encoding='utf-8')
    source=instrument(source)
    source=source.replace('#include "common.h"','#include "common.h"\n#include "build121_cpu_timing.h"',1)
    target.write_text(source,encoding='utf-8')
    (cpu/'build121_cpu_timing.h').write_text((Path(__file__).parent/'native/build121_cpu_timing.h').read_text(encoding='utf-8'),encoding='utf-8')
    run_diff_check(root)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path)
    apply(parser.parse_args().root)
