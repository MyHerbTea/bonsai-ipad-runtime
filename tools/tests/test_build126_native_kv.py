import os,shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class NativeKVTests(unittest.TestCase):
    def test_actual_allocated_tensor_types_empty_mixed_and_streams(self):
        compiler=shutil.which('clang++') or shutil.which('c++')
        if not compiler:
            if os.environ.get('CI'):self.fail('native C++ compiler required in CI')
            self.skipTest('native compiler unavailable on Windows; required in Apple CI')
        import sys
        sys.path.insert(0,str(ROOT/'tools'))
        from rc126_build126_patch_kv_observation import HEADER
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);(d/'kv.h').write_text(HEADER)
            (d/'test.cpp').write_text("""#include <vector>
#include <cassert>
#include "kv.h"
struct T { int type; void *data; };
struct L { T *k,*v; std::vector<T*> k_stream,v_stream; };
int main() {
 int storage=1; T q8{8,&storage},q4{2,&storage},unallocated{8,nullptr};
 std::vector<L> x{{&q8,&q8,{&q8},{&q8}},{&q8,&q8,{},{}}};
 assert(bonsai_allocated_kv_type(x,0)==8 && bonsai_allocated_kv_type(x,1)==8);
 x[1].v=&q4;assert(bonsai_allocated_kv_type(x,1)==-2);
 assert(bonsai_allocated_kv_type(x,0)==8);
 x[0].k_stream.push_back(&q4);assert(bonsai_allocated_kv_type(x,0)==-2);
 x={};assert(bonsai_allocated_kv_type(x,0)==-1);
 x={{&unallocated,&unallocated,{},{}}};assert(bonsai_allocated_kv_type(x,0)==-1);
 assert(bonsai_allocated_kv_type(x,2)==-1);
 assert(bonsai_merge_kv_type(8,2)==-2 && bonsai_merge_kv_type(-1,8)==8);
}""")
            out=d/'test';subprocess.run([compiler,'-std=c++17','-fsanitize=address,undefined',str(d/'test.cpp'),'-o',str(out)],check=True)
            subprocess.run([str(out)],check=True)
if __name__=='__main__':unittest.main()
