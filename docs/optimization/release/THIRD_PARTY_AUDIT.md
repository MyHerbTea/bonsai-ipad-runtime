# Third-party source inventory — T16 draft

**Status:** source inventory recorded; maintainer distribution/license confirmation still required. This document records source-tree evidence and does not make a legal determination.

## Build graph observed

`project.yml` selects `ml-explore/mlx-swift` exactly at `0.31.3`, links `MLX` and `MLXNN`, and embeds `Vendor/llama.xcframework`. At that tag, `Package.swift` declares `apple/swift-numerics` with a `from: "1.0.0"` range. The project now also declares and links Swift Numerics `1.1.1` exactly, constraining that transitive range. The candidate workflow resolves packages after XcodeGen project generation, requires the generated pin to be `1.1.1`, uploads `Package.resolved`, and binds its SHA256 plus normalized package pins/revisions into `artifact_manifest.json`. The current-SHA lock artifact still awaits macOS CI; other transitive versions remain evidenced by that per-build lock, not frozen by this direct pin.

| Component | Exact source evidence | License file evidence | Audit note |
|---|---|---|---|
| MLX Swift | Tag `0.31.3`; `project.yml` exact version | [`LICENSE`](https://github.com/ml-explore/mlx-swift/blob/0.31.3/LICENSE), blob `bb7f03109713c4d9298a4c9e4e24f0f163e4be5e` | Upstream file states MIT. Confirm how required attribution is included in the distributed app. |
| MLX C++ submodule | MLX Swift tag pins `ml-explore/mlx` commit `ce45c52505c8158ea48d2a54e8caae05efd86bfe` | [`LICENSE`](https://github.com/ml-explore/mlx/blob/ce45c52505c8158ea48d2a54e8caae05efd86bfe/LICENSE), blob `98ff47b9ef9d4ac9f1a4bde3db13dd27456c5ea1` | Upstream file states MIT. |
| MLX C API submodule | MLX Swift tag pins `ml-explore/mlx-c` commit `0726ca922fc902c4c61ef9c27d94132be418e945` | [`LICENSE`](https://github.com/ml-explore/mlx-c/blob/0726ca922fc902c4c61ef9c27d94132be418e945/LICENSE), blob `bb7f03109713c4d9298a4c9e4e24f0f163e4be5e` | Upstream file states MIT. |
| `{fmt}` vendored code | MLX Swift tag `0.31.3`, `Source/Cmlx/fmt` | [`LICENSE`](https://github.com/ml-explore/mlx-swift/blob/0.31.3/Source/Cmlx/fmt/LICENSE), blob `1cd1ef92696b65b2ecb0e560e622f0a0e869dcf3` | File contains the MIT terms and an optional exception; retain the exact upstream text if redistributed. |
| nlohmann JSON vendored headers | MLX Swift tag `0.31.3`, `Source/Cmlx/json` | [`LICENSE.MIT`](https://github.com/ml-explore/mlx-swift/blob/0.31.3/Source/Cmlx/json/LICENSE.MIT), blob `1c1f7a690d815db3a79ea3d4c9138a497e2e7702` | Upstream file states MIT. |
| Swift Numerics | `project.yml` directly pins and links `1.1.1`; MLX Swift `0.31.3` allows `from: "1.0.0"` | [`LICENSE.txt` at 1.1.1](https://github.com/apple/swift-numerics/blob/1.1.1/LICENSE.txt), blob `61b0c78195f2d00acaf658000eeca6ad406a3a29` | That version's file is Apache-2.0 with a Runtime Library Exception. The generated current-branch lock remains pending macOS CI. |
| Prism `llama.cpp` | Commit `adfffbe41b2cabcd51fff326ab045662265062bb`; Build83–89 and Build107 patches are applied in CI | [`LICENSE`](https://github.com/PrismML-Eng/llama.cpp/blob/adfffbe41b2cabcd51fff326ab045662265062bb/LICENSE), blob `e7dca554bcb802f98408383a864404e3aa4eacca` | Upstream file states MIT. Verify the notice is carried with the generated XCFramework/app. |
| Local MLX Qwen3 Vision sidecar | `BonsaiLab/BonsaiMLXVisionSidecar.swift` identifies MLX Swift LM `3.31.3`, `Qwen3VL.swift`; the upstream file blob is `22461a92dade5c19d4cf3c58b0aa4a1b018973d7` | MLX Swift LM tag [`LICENSE`](https://github.com/ml-explore/mlx-swift-lm/blob/3.31.3/LICENSE), blob `a8d1c45d4083afe381c7c28e8ebb063b4f9cfc72` | The upstream source file header says `Copyright © 2025 Apple Inc.` and says it is a port from `Blaizzy/mlx-vlm`; the current local notice instead lists only `(c) 2024 ml-explore`. Confirm complete provenance and notices with the maintainer before changing attribution. |
| Model / Vision weights | `project.yml` does not package model weights; Build106 artifact index says weights are external | Per-asset license/source is not present in this repository snapshot | Asset-specific permission and redistribution terms remain unverified; no weights are included in this audit. |
| Apple system frameworks | `project.yml` links Accelerate, Metal, Network, Foundation, Security, and libc++ | Apple SDK/system components | Not third-party vendored app source; release signing/entitlement audit remains separate. |

## Distribution checks still open

1. Swift Numerics is explicitly fixed to `1.1.1`; the workflow also records the full generated lock and binds its digest/pins to the build artifact. Inspect that current-SHA artifact when CI runs. If repeated source builds must use identical versions for every transitive dependency, commit the reviewed generated `Package.resolved`. The current artifact lock remains unverified until the workflow runs.
2. Reconcile the Qwen3 sidecar source header, its stated upstream port, and `THIRD_PARTY_MLX_VISION_NOTICE.md` with the maintainer. Do not silently rewrite the copyright line based on the root package license alone.
3. Decide where full third-party notices ship. The current `project.yml` lists only `release_manifest.json` and `certified_runtime_envelopes.json` as explicit resources; the root notice is not listed there.
4. Verify the generated XCFramework's included source/license set and final signed app payload; the current source scan is not a binary SBOM.
5. Obtain the model and Vision asset license/source for the exact external files selected on device.

**Release gate:** `REVIEW_REQUIRED`. No license-compliance or redistribution-approval claim is made by this inventory.
