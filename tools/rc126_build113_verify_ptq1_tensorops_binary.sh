#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "usage: $0 <llama.framework/llama> [output-dir]" >&2
  exit 2
fi
BIN="$1"
if [ "$#" -eq 2 ]; then OUT="$2"; else OUT="build"; fi
test -f "$BIN"
mkdir -p "$OUT"
STRINGS_FILE="$OUT/ptq1-tensorops-final-binary-strings.txt"
SYMBOLS_FILE="$OUT/ptq1-tensorops-final-binary-symbols.txt"
REPORT="$OUT/PTQ1_TENSOROPS_BINARY_VERIFICATION.txt"
strings "$BIN" > "$STRINGS_FILE"
nm -gU "$BIN" > "$SYMBOLS_FILE"
require_string() {
  grep -Fq -- "$1" "$STRINGS_FILE" || { echo "PTQ1 binary missing string: $1" >&2; exit 1; }
}
require_symbol() {
  grep -Fq -- "$1" "$SYMBOLS_FILE" || { echo "PTQ1 binary missing symbol: $1" >&2; exit 1; }
}
require_string "kernel_mul_mm_ptq1_tensorops_0_f32"
require_string "GGML_METAL_PTQ1_TENSOROPS_DISABLE"
require_string "BONSAI_M5_PTQ1_TENSOR_TRACE_PATH"
require_string "BUILD113_PTQ1_TENSOROPS_INPUT_TYPE_OBSERVED"
require_string "BUILD113_PTQ1_TENSOROPS_ROUTE_SELECTED"
require_string "BUILD113_PTQ1_TENSOROPS_PIPELINE_READY"
require_string "BUILD113_PTQ1_TENSOROPS_DISPATCH_ENQUEUED"
require_string "BUILD113_PTQ1_TENSOROPS_FALLBACK_TO_PRISM"
require_symbol "_ggml_metal_library_get_pipeline_mul_mm_ptq1_tensorops"
BIN_SHA256="$(shasum -a 256 "$BIN" | awk '{print $1}')"
{
  echo "schema=ptq1-metal-tensorops-binary-verification-v1"
  echo "result=PASS_STATIC_LINKAGE_ONLY"
  echo "framework_binary_sha256=$BIN_SHA256"
  echo "embedded_ptq1_metal_kernel_source=true"
  echo "host_pipeline_getter_symbol=true"
  echo "actual_type_and_shape_gate_strings=true"
  echo "runtime_metal_compile=NOT_VERIFIED"
  echo "dispatch_completion=NOT_VERIFIED"
  echo "numerical_correctness=NOT_VERIFIED"
  echo "performance=NOT_MEASURED"
} > "$REPORT"
cat "$REPORT"
echo "PTQ1_TENSOROPS_FINAL_BINARY: PASS (static linkage only)"
