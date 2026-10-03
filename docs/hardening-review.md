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
- Full suite after CI follow-up: **81 passed**. The initial run had 11 text/multiline reference-image failures, also present on the untouched baseline (43 passed, 11 failed). Inspection showed thresholded glyph masks differ only within a one-pixel neighborhood and ink counts differ by less than 1%. Text snapshot comparisons now allow that narrowly bounded raster variation per RGB color; shape comparisons remain exact. Eight comparison regression cases reject missing/recolored text, incorrect canvas dimensions and larger shifts. No reference images were regenerated.
- Correct the renderer fixture to patch `imagegen.core.FontManager`, where the class is actually used, instead of its re-export.
- Ruff correctness checks and `git diff --check` pass.
- Overall integration statement coverage is approximately 24%; services approximately 82%. This is measurement, not a claim of comprehensive coverage.
- No physical AP/BLE upload or Home Assistant 2026.10 validation was performed.

## Recommended follow-up work

1. Retain the strict shape snapshots and bounded text comparisons when expanding rendering tests; use explicit semantic assertions for new layout features.
2. Add config-flow, migration, websocket reconnect, AP recovery and dynamic tag lifecycle tests before structural refactoring. Current tests still primarily cover rendering and the new service/queue behavior.
3. Expose a public force-refresh method on the tag type manager; `refresh_tag_types_service` still writes `manager._last_update` directly.
4. Resolve the no-op `async_remove_invalid_ble_entities` migration after defining exactly which entities should be removed. Deleting registry entries without those rules would be unsafe.
5. Migrate requests-based AP HTTP operations to the HA aiohttp session. Existing requests operations are executor-backed; this is an async architecture/cancellation improvement, not evidence they currently block the event loop directly.
6. Remove the unused `websocket-client` dependency after a dedicated packaging check; code imports `websockets`, not `websocket`.
7. Split the 1,470-line coordinator and 759-line integration setup into focused API, websocket, storage and migration components once behavior is covered.
8. Add payload types and expand lint/type checks gradually. The current Ruff rules target correctness rather than mass reformatting.
9. Verify against the intended HA deployment version and exercise real AP/BLE uploads before installing this branch in production.

## CI metadata follow-up

Hassfest rejected Pillow in the manifest because HA itself provides it. Remove that redundant requirement and declare `CONFIG_SCHEMA` with `cv.config_entry_only_config_schema(DOMAIN)` to clear the configuration-schema warning.

HACS rejected this fork because Issues are disabled and repository topics are empty. These two checks concern eligibility for the HACS default catalog, not custom-repository integration packaging. The HACS workflow ignores `issues topics` **only when `github.event.repository.fork` is true**; all integration checks remain enabled, and non-fork repositories retain the complete catalog validation. No repository settings were changed.
