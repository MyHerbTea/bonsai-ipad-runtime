# Minimal unblock for the flag16 device decision — 2026-10-24

User authorized starting the short path: preflight (10 minute target), truthful minimal API-cancel recovery only if quarantined, then one new flag16 ABBA (512 prompt /128 formal output, two warmups per slot,12 inference requests). No other candidate, automatic retry, or full rerun. Stop on uncertain inference, identity change or recovery failure. Runtime budget for the measurement is45 minutes; no automatic extra round.

This supersedes the broad Build120 recovery/export plan. Keep the same checkout and candidate branch; preserve previous commits/evidence. No snapshot HTTP export, Markdown changes, new monitoring infrastructure, or new CPU math. The existing exclusive acknowledgement operation will accept a separately validated operator-confirmed API cancellation, persist/read the audit internally, compare the exact Quick marker before deletion, and preserve B16. Historical cancellation identity and current accepting IPA identity remain distinct.

Implementation: existing recovery helper + small typed proof validator; existing Python CLI + bounded offline cancellation-evidence validator. Existing Build119 regressions and new focused recovery tests run in existing CI. The paused snapshot tests remain archived source, outside this delivery's test selection. Readback claimed by the client is server-side store verification, not independent HTTP snapshot export.

Progress: initial device connection refused at the last known address. User prompted to enable API/provide current address. No inference or device mutation. Existing local Build120 Python tests remain RED because implementation is missing. Git HTTPS read access works with per-command http.sslBackend=openssl; no global Git configuration change.
