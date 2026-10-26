#!/usr/bin/env python3
"""Read allocated KV tensors; no changes to allocation, math or fallback."""
from pathlib import Path
import argparse
from rc126_build113_patch_prism_ptq1_tensorops import BASE_SHA, run_git, run_diff_check

HEADER = r"""#pragma once
// Read every allocated layer, including per-stream views. -1 unknown/empty, -2 mixed.
static inline int bonsai_merge_kv_type(int a, int b) {
    if (a == -2 || b == -2) return -2;
    if (a < 0) return b;
    if (b < 0) return a;
    return a == b ? a : -2;
}
template<class Layers> static int bonsai_allocated_kv_type(const Layers & layers, int which) {
    if (which != 0 && which != 1) return -1;
    int result = -1;
    for (const auto & layer : layers) {
        const auto * tensor = which == 0 ? layer.k : layer.v;
        if (tensor && tensor->data) result = bonsai_merge_kv_type(result, int(tensor->type));
        const auto & streams = which == 0 ? layer.k_stream : layer.v_stream;
        for (const auto * view : streams)
            if (view && view->data) result = bonsai_merge_kv_type(result, int(view->type));
    }
    return result;
}
"""

def once(s,a,b):
    if s.count(a)!=1: raise SystemExit('Build126 source drift: '+a[:90])
    return s.replace(a,b,1)

def apply(root):
    if run_git(root,'rev-parse','HEAD') != BASE_SHA: raise SystemExit('wrong pinned Prism revision')
    src=root/'src'
    p=src/'llama-memory.h';s=p.read_text()
    s=once(s,'    virtual bool get_can_shift() const = 0;',
        '    virtual int bonsai_kv_type(int) const { return -1; }\n    virtual bool get_can_shift() const = 0;')
    p.write_text(s)
    p=src/'llama-kv-cache.h';s=p.read_text()
    s=once(s,'#include "llama-memory.h"','#include "llama-memory.h"\n#include "bonsai-build126-kv-types.h"')
    s=once(s,'    ~llama_kv_cache() = default;',
        '    ~llama_kv_cache() = default;\n    int bonsai_kv_type(int which) const override { return bonsai_allocated_kv_type(layers, which); }')
    p.write_text(s)
    for file,cls,body in [
        ('llama-kv-cache-iswa.h','llama_kv_cache_iswa','return bonsai_merge_kv_type(kv_base ? kv_base->bonsai_kv_type(which) : -1, kv_swa ? kv_swa->bonsai_kv_type(which) : -1);'),
        ('llama-memory-hybrid.h','llama_memory_hybrid','return get_mem_attn() ? get_mem_attn()->bonsai_kv_type(which) : -1;'),
        ('llama-memory-hybrid-iswa.h','llama_memory_hybrid_iswa','return get_mem_attn() ? get_mem_attn()->bonsai_kv_type(which) : -1;')]:
        p=src/file;s=p.read_text()
        s=once(s,'    bool get_can_shift() const override;',
            '    int bonsai_kv_type(int which) const override { '+body+' }\n    bool get_can_shift() const override;')
        p.write_text(s)
    (src/'bonsai-build126-kv-types.h').write_text(HEADER)
    p=src/'llama-context.cpp';s=p.read_text()
    declarations = """// BONSAI_KV_OBSERVATION_126: thread-local failure and read-only allocated tensor proof.
static thread_local std::string bonsai_context_failure;
extern "C" __attribute__((visibility("default"))) const char * BonsaiNativeContextFailure(void) {
    return bonsai_context_failure.c_str();
}
extern "C" __attribute__((visibility("default"))) int BonsaiNativeKVCacheType(llama_context * ctx, int which) {
    if (!ctx || !ctx->get_memory()) return -1;
    return ctx->get_memory()->bonsai_kv_type(which);
}

"""
    s=once(s,'llama_context * llama_init_from_model(',declarations+'llama_context * llama_init_from_model(')
    s=once(s,'        llama_context_params   params) {\n    if (!model) {',
        '        llama_context_params   params) {\n    bonsai_context_failure = "NATIVE_CONTEXT_PARAMETERS_REJECTED_SEE_LOG";\n    if (!model) {')
    s=once(s,'        auto * ctx = new llama_context(*model, params);\n        return ctx;',
        '        auto * ctx = new llama_context(*model, params);\n        bonsai_context_failure.clear();\n        return ctx;')
    s=once(s,'        LLAMA_LOG_ERROR("%s: failed to initialize the context: %s\\n", __func__, err.what());',
        '        bonsai_context_failure = err.what();\n        LLAMA_LOG_ERROR("%s: failed to initialize the context: %s\\n", __func__, err.what());')
    p.write_text(s)
    run_diff_check(root)
    print('Build126 allocated KV tensor observation and native failure reason: source patch PASS')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('prism_dir',type=Path)
    apply(parser.parse_args().prism_dir.resolve())
