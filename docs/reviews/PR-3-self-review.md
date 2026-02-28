# PR-3 Self-Review: Parametrized scheduler executor tests

## What I changed and why

I added `test_scheduler_executor_parametrized.py` with 6 test methods, each parametrized over LocalExecutor and CeleryExecutor (12 cases total). The tests make sure the scheduler interacts correctly with the executor by checking:

- `executor.start()` is called once
- `executor.job_id` is set to the scheduler’s job ID
- `executor.heartbeat()` is called at least once
- `executor.get_event_buffer()` is read in the loop
- `executor.end()` is called on shutdown
- Slot attributes are visible to the scheduler

## Why unit tests

The executor is fully mocked—no real Celery broker or Kubernetes. We’re only testing the scheduler’s contract with the executor interface.

## What I didn’t cover

- Real queueing/dequeueing would need a more realistic (or queue-aware) mock.
- I didn’t include KubernetesExecutor because it needs the cncf.kubernetes provider, which isn’t always there in test envs.
- Multi-executor (primary + secondary) is already covered in `test_scheduler_job.py`, so I didn’t duplicate it.

## Follow-ups

- If the executor lifecycle API changes (e.g. `start` is renamed), these tests should catch it for each backend.
- We could add KubernetesExecutor or custom executors to the parametrization later for more coverage.
