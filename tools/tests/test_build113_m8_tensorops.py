import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import rc126_build113_patch_prism_ptq1_tensorops as p
import rc126_build113_patch_prism_m5_nax_pq2 as scaffold

class M8TensorOps(unittest.TestCase):
    def test_m8_route_and_safe_tile_bounds(self):
        source=Path(p.__file__).read_text(encoding="utf-8")
        self.assertIn("ne11 == 8 ||",source)
        kernel=p.derive_ptq1_kernel(scaffold.KERNEL)
        self.assertIn("M - 1",kernel)
        self.assertIn("if (r >= M)",kernel)
        self.assertIn("if (col + j < N)",kernel)

if __name__ == "__main__": unittest.main()
