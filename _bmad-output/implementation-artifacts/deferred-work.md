# Deferred Work

## Deferred from: code review of 1-3-custom-backend-adapter (2026-07-15)

- pyproject.toml test deps — pre-existing, not in scope for this story's ACs
- CustomGenerator not re-exported from adapters/__init__.py — not required by spec
- Timezone-naive datetime.now() — can be addressed when multi-zone support needed

## Deferred from: code review of 1-3-custom-backend-adapter (2026-07-16)

- Timezone-naive datetime.now() [custom_generator.py:82] — pre-existing, re-deferred
- Empty colors list fallback to black [domain/services.py:33] — pre-existing domain code, out of scope for this story
- n_clusters upper bound [custom_generator.py:47] — performance concern (cap at 40000 for 200x200 images), not a correctness issue

## Deferred from: code review of 1-5-local-processor-generation-service (2026-07-16)

- success=True hardcoded without post-generation validation [local_processor.py:47,70] — matches current spec
- generator.generate() exceptions propagate raw across port boundary [local_processor.py:43,66] — design choice
- request.image_path not validated before use [local_processor.py:43,66] — out of scope for this story
- settings parameter silently ignored [local_processor.py:34,57] — AppSettings is a known placeholder

## Deferred from: code review of 1-6-cli-generate-command (2026-07-16)

- Backend generators eagerly instantiated [factory.py:28-30] — low overhead (stubs + no custom __init__)
- Hardcoded /tmp/color-scheme output dir [main.py:36] — out of scope (Epic 2 adds -o/--output-dir)
- `.` in pythonpath is a fixture hazard [pyproject.toml:25] — pre-existing, not specific to this change
- Only ColorSchemeError caught [main.py:47] — by design per spec ("let unexpected errors propagate")
- Callback has no error handling for factory failures [main.py:22-26] — low risk, systemic config issues handled at app level
- CliDependencies.processor field declared but never set [factory.py:23] — forward-looking, will be used in Epic 2/3
