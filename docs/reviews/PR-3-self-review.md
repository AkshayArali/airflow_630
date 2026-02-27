# PR-3 Self-Review: Strengthen scheduler job tests with parametrized executor backends

## What changed and why?

Added `test_scheduler_executor_parametrized.py` with 6 test methods, each parametrized
across **LocalExecutor** and **CeleryExecutor** backends (12 test cases total). The tests
verify that the scheduler correctly interacts with any executor type by asserting:

- `executor.start()` is called exactly once
- `executor.job_id` is assigned the scheduler's job ID
- `executor.heartbeat()` is called at least once
- `executor.get_event_buffer()` is read during the loop
- `executor.end()` is called on shutdown
- Slot availability attributes are visible to the scheduler

## Why is this the right test layer (unit/integration/UI)?

**Unit** — the executor is fully mocked, so no actual task execution, Celery broker,
or Kubernetes cluster is needed. The tests focus on the scheduler's protocol-level
interactions with the executor interface.

## What could still break / what's not covered?

- Actual task queueing and dequeuing behavior (requires a real or more sophisticated
  mock executor with queue semantics).
- The `KubernetesExecutor` is not included because its import path requires the
  `cncf.kubernetes` provider, which may not be installed in all test environments.
- Multi-executor scenarios (primary + secondary) are tested in the existing
  `test_scheduler_job.py` and are not duplicated here.

## What risks or follow-ups remain?

- If the executor lifecycle API changes (e.g., `start` is renamed), these tests will
  surface the breakage for each backend type independently.
- A future parametrization over `KubernetesExecutor` or custom executors would
  further broaden coverage.
