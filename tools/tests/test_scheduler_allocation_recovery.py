"""Fault injection into the actual pinned scheduler allocation block (no model)."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class SchedulerAllocationTests(unittest.TestCase):
    def allocation_block(self):
        prism = Path(os.environ.get('BONSAI_PRISM_TEST_DIR', str(ROOT / 'deliveries/prism-source')))
        path = prism / 'ggml/src/ggml-backend.cpp'
        if not path.exists():
            self.skipTest('pinned patched dependency required')
        source = path.read_text(encoding='utf-8-sig')
        start = source.index('    sched->context_buffer_size = ggml_sched_max_splits*')
        end = source.index('    const int initial_splits_capacity = 16;', start)
        return source[start:end]

    def test_allocation_recovery_is_independent_of_trace(self):
        block = self.allocation_block()
        self.assertNotIn('getenv("BONSAI_BUILD84_TRACE_PATH")', block,
                         'B8/16K tracing is off; recovery must still run')
        self.assertIn('BUILD115_SCHED_ALLOC_EXHAUSTED', block)

    def test_actual_allocation_block_with_failed_allocators(self):
        compiler = shutil.which('clang++') or shutil.which('c++') or shutil.which('g++')
        if not compiler or os.name == 'nt':
            self.skipTest('macOS CI compiles and runs actual Apple recovery block')
        block = self.allocation_block()
        # Only the Apple allocation region is compiled; injected allocators make
        # each failure deterministic, without trying to exhaust host RAM.
        block = block.replace('#if defined(__APPLE__)', '#if 1')
        preamble = r'''
#include <cassert>
#include <cstddef>
#include <cstdio>
#include <cstdlib>
#include <cerrno>
#include <sys/mman.h>
static int mode, malloc_calls, mmap_calls, free_calls;
static void * fault_malloc(size_t n) {
    ++malloc_calls;
    if (mode == 1 && malloc_calls == 1) return nullptr;
    if (mode >= 2) return nullptr;
    return std::malloc(n);
}
static void fault_free(void * p) { if (p) ++free_calls; std::free(p); }
static void * fault_mmap(void * p, size_t n, int prot, int flags, int fd, off_t offset) {
    ++mmap_calls;
    return mode == 3 ? MAP_FAILED : ::mmap(p, n, prot, flags, fd, offset);
}
static void bonsai_build84_trace(const char *, ...) {}
struct ggml_tensor { char payload[64]; };
static size_t ggml_tensor_overhead() { return 128; }
static size_t ggml_graph_overhead_custom(size_t n, bool) { return n * 16; }
struct Hash { size_t size; };
static void ggml_hash_set_free(Hash *) {}
struct Sched {
    char * context_buffer; size_t context_buffer_size; bool context_buffer_mmap;
    Hash hash_set; int n_backends, n_copies;
    void * hv_tensor_backend_ids, * hv_tensor_copies, * node_backend_ids;
    void * leaf_backend_ids, * prev_node_backend_ids, * prev_leaf_backend_ids;
};
#define GGML_SCHED_MAX_SPLIT_INPUTS 16
#define malloc fault_malloc
#define free fault_free
#define mmap fault_mmap
static Sched * allocate() {
    Sched * sched = (Sched *) std::calloc(1, sizeof(Sched));
    sched->hash_set.size = 257; sched->n_backends = 2; sched->n_copies = 1;
    const size_t graph_size = 128, ggml_sched_max_splits = graph_size;
'''
        checks = r'''
    return sched;
}
#undef malloc
#undef free
#undef mmap
int main() {
    for (bool tracing : {false, true}) {
        if (tracing) setenv("BONSAI_BUILD84_TRACE_PATH", "/dev/null", 1);
        else unsetenv("BONSAI_BUILD84_TRACE_PATH");
        for (mode = 0; mode != 4; ++mode) {
            malloc_calls = mmap_calls = free_calls = 0;
            Sched * sched = allocate();
            if (mode == 3) {
                assert(sched == nullptr); assert(malloc_calls == 2); assert(mmap_calls == 1);
                assert(free_calls == 1); // constructor itself is released
                continue;
            }
            assert(sched && sched->context_buffer); // ggml_init's exact precondition
            assert(((size_t)sched->context_buffer % 16) == 0);
            assert(malloc_calls == (mode == 0 ? 1 : 2));
            assert(mmap_calls == (mode == 2 ? 1 : 0));
            assert(sched->context_buffer_mmap == (mode == 2));
            if (sched->context_buffer_mmap) assert(::munmap(sched->context_buffer, sched->context_buffer_size) == 0);
            else std::free(sched->context_buffer);
            std::free(sched);
        }
    }
    puts("Scheduler actual-block fault injection: 8 cases PASS");
}
'''
        preamble = '#include <initializer_list>\n' + preamble
        (ROOT / 'deliveries').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='scheduler-fault-', dir=ROOT / 'deliveries') as folder:
            cpp = Path(folder) / 'scheduler.cpp'
            binary = Path(folder) / 'scheduler-test'
            cpp.write_text(preamble + block + checks, encoding='utf-8')
            subprocess.run([compiler, '-std=c++17', str(cpp), '-o', str(binary)], check=True, capture_output=True, text=True)
            result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
            self.assertIn('8 cases PASS', result.stdout)


if __name__ == '__main__':
    unittest.main()
