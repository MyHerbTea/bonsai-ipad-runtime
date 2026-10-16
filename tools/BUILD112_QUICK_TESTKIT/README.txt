Bonsai Build112 Quick TestKit

This is intentionally a small measurement tool, not a certification harness.

What it does
1. Checks the connected app is Build112.
2. Checks 32768 context and the actual PERFORMANCE16 16/16 runtime profile.
3. Runs one warmup and six measured deterministic text requests at approximately 512, 2048 and 8192 prompt-token targets.
4. Captures prefill, TTFT, decode rate, and memory/thermal telemetry.
5. Produces one ZIP under RESULTS.

What it does NOT do
- No checkpoint/resume.
- No B8/B16 arm switching.
- No SAFE4 manipulation.
- No runtime configuration changes.
- No automatic inference retry.
- No certification claim.
- No automatic B8 comparison.

Use
1. Extract this folder.
2. Double-click RUN_BUILD112_QUICK_TEST.cmd.
3. Press Enter for the default Base URL if it is correct.
4. Enter the API Key once.
5. Send the resulting ZIP to ChatGPT for analysis.

The test is designed for the already-installed Build112 IPA. It does not require reinstalling the IPA.
