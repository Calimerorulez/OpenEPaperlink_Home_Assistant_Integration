# Service and upload hardening review

Reviewed against `f28c21761365181cfaf203030678f1c29433baf3`.

## Implemented

- Resolve the OpenEPaperLink identifier explicitly rather than taking the first device identifier. Preserve BLE prefix handling and validation of missing/foreign devices.
- Copy explicit device targets before label/area expansion so service data is not mutated; deduplicate overlapping targets.
- Generate and enqueue all target uploads before waiting. Each queued upload returns its own completion future, so simultaneous calls cannot consume each other's errors or wait for unrelated queues.
- Attribute upload failures to their actual device and continue other targets after validation, operational or BLE errors.
- Reserve upload capacity before starting each task. Previously `_active_uploads` was never incremented, allowing unbounded concurrency and negative counters. Mark the processor active before scheduling it to prevent duplicate processors from immediate enqueues.
- Shield accepted upload futures from caller cancellation.
- Remove unreachable warning code after payload validation raises.
- Replace `async_timeout` with `asyncio.timeout` in coordinator and uploads; the integration did not declare the former dependency and current HA no longer installs it automatically.
- Run correctness-focused Ruff checks and report coverage in CI. Update CI to Python 3.14; remove obsolete pip/colorlog/Ruff pins that conflict with current dependencies and include missing NumPy and BLE retry dependencies in development requirements.

## Validation

Python 3.14.7, Home Assistant 2026.9.4, dependencies installed from the repository requirements:

- 19 new service/queue regression cases pass, including bounded concurrency (limits 1 and 2), processor restart, overlapping targeting, simultaneous calls, continued processing after errors and caller cancellation.
- Full suite: 62 passed, 11 failed. The same 11 image comparison failures occur on the untouched baseline (43 passed, 11 failed) in the same environment. They concern text/multiline reference images; their root cause has not been established. No reference images were regenerated to hide these failures.
- Ruff correctness checks and `git diff --check` pass.
- Overall integration statement coverage is approximately 25%; services approximately 81%. This is measurement, not a claim of comprehensive coverage.
- No physical AP/BLE upload or Home Assistant 2026.10 validation was performed. The full CI job is expected to remain red until the existing reference-image failures are addressed.

## Recommended follow-up work

1. Diagnose the existing text/multiline reference-image failures with controlled Pillow/font/rendering versions before updating image expectations.
2. Add config-flow, migration, websocket reconnect, AP recovery and dynamic tag lifecycle tests before structural refactoring. Current tests still primarily cover rendering and the new service/queue behavior.
3. Expose a public force-refresh method on the tag type manager; `refresh_tag_types_service` still writes `manager._last_update` directly.
4. Resolve the no-op `async_remove_invalid_ble_entities` migration after defining exactly which entities should be removed. Deleting registry entries without those rules would be unsafe.
5. Migrate requests-based AP HTTP operations to the HA aiohttp session. Existing requests operations are executor-backed; this is an async architecture/cancellation improvement, not evidence they currently block the event loop directly.
6. Remove the unused `websocket-client` dependency after a dedicated packaging check; code imports `websockets`, not `websocket`.
7. Split the 1,470-line coordinator and 759-line integration setup into focused API, websocket, storage and migration components once behavior is covered.
8. Add payload types and expand lint/type checks gradually. The current Ruff rules target correctness rather than mass reformatting.
9. Verify against the intended HA deployment version and exercise real AP/BLE uploads before installing this branch in production.
