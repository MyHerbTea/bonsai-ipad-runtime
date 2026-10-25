# Build124 SDOT candidate

Source branch codex/build124-sdot, base aa7404fb86723b81327cf484ae853caf95713bb6. Official checkout D:/codexSpace/bonsai-ipad-runtime.

Approved change: independent wire flag64, B8 Quick, counting off. Preserve original baseline unpack, traversal, four Q8 scales and float accumulation order. Only each 32-element signed integer dot changes to two SDOT operations. Apple ARM64 sysctl hw.optional.arm.FEAT_DotProd must confirm support; failed lookup disables the capability. A noinline target(dotprod) clone isolates specialized instructions. No new timers or per-dot shared counters. No runtime defaults/promotion.

Local RED-to-GREEN patch preservation and assembly-gate tests executed. Actual Apple ARM64 parity/sanitizers, Swift admission, iOS build and generated framework assembly checks are PENDING_CI, not PASS. No device requests or performance result. The existing generic multi-candidate CLI retains its original candidates/counting behavior; the new opt-in candidate uses the existing API with counting_enabled=false after identity/install checks.

CI includes finite varied half scales, signed activation extremes, packed byte coverage, zero/multiple blocks and contraction off/on. It saves fixture iOS assembly and actual framework disassembly; missing SDOT, an unrecognized block loop or vector stack stores inside the candidate loop stop delivery. Full disassembly retained for manual inspection; this static gate does not prove speedup or complete liveness.

Repository-wide documentation checker reports pre-existing ignored deliveries/ source/archive documents as unclassified or having broken links. These unrelated historical deliveries are not edited. The documentation unit tests have three failures caused by these same deliveries: test_active_workspace_conflicts_fail_but_history_is_allowed, test_development_head_can_differ_from_main, and test_repository_navigation_and_authority_are_consistent. The checker reports 165 entries, all under deliveries/, and no new non-delivery document errors. Full outputs are recorded in local-checks.json and its referenced logs.

The next external step is a concrete Build124 source push to the public origin and Apple CI, subject to repository authorization. No additional device measurements before build/assembly/identity gates and installation.

Capability reference: [Apple instruction-set detection](https://developer.apple.com/documentation/kernel/1387446-sysctlbyname/determining_instruction_set_characteristics).
