# Build117 source map

- Workspace: `D:\codexSpace\iPad27B\bonsai-ipad-runtime` (explicit current user instruction overrides repository AGENTS.md directory policy).
- Origin: https://github.com/MyHerbTea/bonsai-ipad-runtime
- Base: `4dce38a80ddfbfe186c3af052cb4932012367a70`, matching Build116 TestKitIdentity.json and remote `codex/ptq1-oneclick-tournament`.
- Branch: `codex/build117-diagnostics`; main is older and is not the benchmark starting point.
- App: `BonsaiLab/`; XcodeGen `project.yml` includes this directory recursively. Swift bridging header: `BonsaiLab/MTMDProbeBridge.h`.
- API: `LocalOpenAIServer.swift`; inference: `BonsaiEngine.swift`; benchmark lease: `BenchmarkSessionManager.swift` / `BenchmarkSessionControl`.
- Native: Prism pinned `adfffbe41b2cabcd51fff326ab045662265062bb`, fetched and patched by `.github/workflows/build-ptq1-tournament.yml`; no native source/framework bundled in git.
- Runner: `tools/PTQ1_ONECLICK/`; packaging: `tools/package_ptq1_oneclick.py`.
- Baseline: Python 3.11.4, existing runner unittest suite 10/10 PASS (`evidence/baseline-oneclick.txt`).
- Host: Windows; no local Swift, Xcode or connected iPad build/test capability detected. Apple compilation and runtime assertions remain pending external environment.
- Historical IPA/results are outside this clone and will not be overwritten.

Plan: `../superpowers/plans/2026-10-23-build117-complete-task-plan.md` (repository mirror; authoritative status also maintained in the parent workspace).
