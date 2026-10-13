# Bonsai RC1.26 Build106 · M5 12GB Runtime Governor

**Status: CI candidate. Device certification is pending.**

Baseline: Build105 4c25b0abd79d316754b0e612ab7c5fa53cabffd6.

Build106 maps the existing Build94 certified/consent-gated launch arm to an explicit runtime profile at **llama context creation**. It cannot switch n_batch or n_ubatch per HTTP request on an already allocated context.

SAFE4 = 4/4 for sticky recovery. BALANCED8 = 8/8 conservative normal 32K default. PERFORMANCE16 = 16/16 for qualified explicit launch. TURBO24 = 24/24 for qualified explicit launch. LEGACY32 = 32/32 preserved legacy explicit consent-gated Build102 experiment, never auto-promoted.

Build105 32768 context, n_seq_max=1, KV reuse disabled, OpenAI text/vision/SSE, and server output limits are preserved.

`GET /debug/build106/governor` (authenticated) displays actual active batch/ubatch, chosen profile, reason, and next-process fallback boundary.

GitHub Actions packages an **unsigned** IPA and `Bonsai-Build106-OneClick-FullStage.zip` (Windows test GUI). Unsigned IPA needs signing/sideload before installation. Extract the test ZIP, double-click `RUN_BUILD106_FULL_STAGE.cmd`, enter the LAN API host and API Key. Python 3.8+ required. Key is not written into reports. iPad API must already be running; Windows cannot restart a terminated iPad app over HTTP.

Checks: Build106 identity, governor active shape, output >256, SSE, multi-turn, long input, 1–3 images, post-vision text and KV quarantine. Collected reports are zipped under RESULTS. Build/CI status never counts as device certification or evidence of faster tokens/s.
