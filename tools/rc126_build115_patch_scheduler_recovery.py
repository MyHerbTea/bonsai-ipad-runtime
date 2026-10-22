#!/usr/bin/env python3
"""Remove tracing as a prerequisite for scheduler allocation failure recovery.

Apply after patches 83..89 and 114, to the same pinned Prism revision.
Successful original allocations, capacity rules, tensors and kernels are unchanged.
"""
import argparse
from pathlib import Path
from rc126_build113_patch_prism_ptq1_tensorops import BASE_SHA, run_git, run_diff_check


def apply(root):
    if run_git(root, 'rev-parse', 'HEAD') != BASE_SHA:
        raise SystemExit('wrong pinned Prism revision')
    path = root / 'ggml/src/ggml-backend.cpp'
    source = path.read_text(encoding='utf-8')
    start = source.index('    sched->context_buffer_size = ggml_sched_max_splits*')
    end = source.index('    const int initial_splits_capacity = 16;', start)
    block = source[start:end]
    old = 'sched->context_buffer == NULL && getenv("BONSAI_BUILD84_TRACE_PATH") != NULL'
    if block.count(old) != 2 or 'BUILD89_COMPACT_BUDGET' not in block:
        raise SystemExit('expected exactly two inherited trace-gated recovery paths')
    block = block.replace(old, 'sched->context_buffer == NULL')
    block = block.replace('// 32K-only recovery: anonymous mmap reserves a contiguous virtual range',
                          '// Build115: allocation recovery is independent of trace/context shape.\n'
                          '    // Anonymous mmap reserves a contiguous virtual range')
    # Move exhausted-allocation cleanup outside the Apple mmap branch so no
    # supported platform passes a NULL external pool to ggml_init for a retry.
    cleanup_start = block.index('        if (sched->context_buffer == NULL) {\n')
    cleanup_end = block.index('    }\n#endif', cleanup_start)
    cleanup = block[cleanup_start:cleanup_end]
    if not cleanup.endswith('        }\n') or cleanup.count('return NULL;') != 1:
        raise SystemExit('unexpected inherited cleanup block')
    block = block[:cleanup_start] + block[cleanup_end:]
    cleanup = '\n'.join(line[4:] if line.startswith('    ') else line for line in cleanup.splitlines()) + '\n'
    cleanup = cleanup.replace('BUILD88_SCHED_ALLOC_EXHAUSTED', 'BUILD115_SCHED_ALLOC_EXHAUSTED')
    block += '    // BONSAI_SCHEDULER_RECOVERY_115: no allocation success is inferred from logging.\n' + cleanup + '\n'
    path.write_text(source[:start] + block + source[end:], encoding='utf-8')
    run_diff_check(root)
    print('Build115 scheduler recovery: source patch PASS; device startup pending')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('prism_dir', type=Path)
    apply(parser.parse_args().prism_dir.resolve())
