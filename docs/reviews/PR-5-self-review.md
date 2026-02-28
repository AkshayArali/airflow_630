# PR-5 Self-Review: Document flakiness in quarantined test_step_by_step

## What I changed and why

I replaced the short `# FIXME` on the `@pytest.mark.quarantined` decorator for `test_step_by_step` in `test_mapped_task_upstream_dep.py` with a clearer explanation:

1. **Root cause** — The test keeps using a `schedulable_tis` dict from an earlier scheduling iteration. In the `UPSTREAM_FAILED` branch the return value of `_one_scheduling_decision_iteration()` is thrown away (around line 234), so later `.run()` calls on `t3` and `t4` use stale TaskInstance objects. Whether that still works depends on SQLAlchemy’s session state, which can vary.

2. **What would fix it** — Always use the return value of `_one_scheduling_decision_iteration`, get TIs from the latest snapshot, and maybe call `session.expire_all()` between iterations.

3. **Why it’s still quarantined** — Fixing it properly means touching all 12 parametrized cases and several code paths, and it’s tied to scheduler internals. I’d want a careful pass and a lot of runs before re-enabling.

## Why this is still “unit” (with a caveat)

The test itself is unit-level (in-process, dag_maker), but the flakiness comes from session/ORM behavior across iterations, which is more integration-y. I documented that so the next person can decide whether to fix it as-is or refactor.

## What I didn’t cover

- I only documented `test_step_by_step`. The whole `test_impersonation_tests.py` module is also quarantined and needs Breeze, so I left that out of scope.
- I didn’t reproduce the flakiness locally; the analysis is from reading the code and the GitHub issue, since running it needs DB fixtures.

## Follow-ups

- Someone should try the suggested fix (capture return values, expire session) and run the 12 combinations at least 10 times locally.
- If upstream fixes Apache Airflow issue #38955, we should update this comment or remove the quarantine.
