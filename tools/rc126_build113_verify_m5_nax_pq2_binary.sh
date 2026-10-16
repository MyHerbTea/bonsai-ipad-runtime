#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "usage: $0 <llama.framework/llama> [output-dir]" >&2
  exit 2
fi

BIN="$1"
OUT="${2:-build}"
test -f "$BIN"
mkdir -p "$OUT"

STRINGS_FILE="$OUT/m5-nax-pq2-final-binary-strings.txt"
SYMBOLS_FILE="$OUT/m5-nax-pq2-final-binary-symbols.txt"
REPORT="$OUT/M5_NAX_PQ2_BINARY_VERIFICATION.txt"

strings "$BIN" > "$STRINGS_FILE"
nm -gU "$BIN" > "$SYMBOLS_FILE"

require_string() {
  if ! grep -Fq -- "$1" "$STRINGS_FILE"; then
    echo "M5-NAX-PQ2 final binary missing embedded string: $1" >&2
    exit 1
  fi
}

require_symbol() {
  if ! grep -Fq -- "$1" "$SYMBOLS_FILE"; then
    echo "M5-NAX-PQ2 final binary missing native symbol: $1" >&2
    exit 1
  fi
}

# This Prism revision runtime-compiles Metal kernels from embedded source.
# These checks prove the source and host dispatch path are packaged; they do
# not claim that a device successfully compiled or executed the kernel.
require_string "kernel_mul_mm_nax_pq2_0_f32"
require_string "GGML_METAL_PQ2_NAX_DISABLE"
require_string "BONSAI_M5_NAX_PQ2_TRACE_PATH"
require_string "BUILD113_M5_NAX_PQ2_ROUTE_SELECTED"
require_string "BUILD113_M5_NAX_PQ2_PIPELINE_READY"
require_string "BUILD113_M5_NAX_PQ2_DISPATCH_ENQUEUED"
require_symbol "_ggml_metal_library_get_pipeline_mul_mm_nax_pq2"

BIN_SHA256="$(shasum -a 256 "$BIN" | awk '{print $1}')"
{
  echo "schema=m5-nax-pq2-binary-verification-v1"
  echo "result=PASS_STATIC_LINKAGE_ONLY"
  echo "framework_binary_sha256=$BIN_SHA256"
  echo "embedded_metal_kernel_source=true"
  echo "host_pipeline_getter_symbol=true"
  echo "host_route_trace_markers=true"
  echo "runtime_metal_compile=NOT_VERIFIED"
  echo "device_dispatch=NOT_VERIFIED"
  echo "numerical_correctness=NOT_VERIFIED"
  echo "performance=NOT_MEASURED"
} > "$REPORT"

cat "$REPORT"
echo "M5_NAX_PQ2_FINAL_BINARY: PASS (static linkage only)"
