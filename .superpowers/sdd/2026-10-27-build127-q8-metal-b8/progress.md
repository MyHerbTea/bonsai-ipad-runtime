# SDD ledger — plan: docs/superpowers/plans/2026-10-27-build127-q8-metal-b8.md

Base: 2b4daf44ff9f8b7d2bb30f9831c53938fc7bd158
Branch: codex/build127-q8-metal-b8

Task 1: candidate policy and gate regression tests implemented. Local Python tests pass; C++ compilation is deferred to macOS CI because this Windows host has no C++ compiler.
Task 2: pinned-Prism patcher adds one M5/PTQ1/F32 contiguous B8 `r1_8` route; CPU flag64 is preserved, unsupported inputs stay on `r1_4`, and an unavailable `r1_8` pipeline retries `r1_4` with explicit counter evidence. Actual build and MSL compile await CI.
Task 3: bounded 16K/B8/Q8_0 ABBA Quick harness implemented. Runtime regressions caught and fixed: duplicate `keep_text` forwarding, and incorrectly requiring the pre-experiment context ID after intentional context recreation. Restored production context is now validated as a new stable Q8 context across two ordinary API calls.
Task 4: workflow and delivery packaging are wired; remote CI and IPA/TestKit generation have not run.
Task 5: local verification complete. Build127 focused tests: 11 passed, 2 skipped (actual patched Prism checkout and C++ compiler unavailable); Build126 regression tests: 15 passed, 1 native compiler skip; portable OneClick tests: 16 passed. Changed Python syntax, dry-run, tracked-source documentation audit, workflow YAML syntax and git diff --check pass. Swift/C++/Metal compilation, macOS CI, IPA/TestKit artifact generation and M5 Quick are NOT_RUN. No performance result or release claim exists.
