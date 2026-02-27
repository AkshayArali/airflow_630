# PR-5 Self-Review: Fix or document flakiness in quarantined test_step_by_step

## What changed and why?

Added detailed inline documentation to the `@pytest.mark.quarantined` decorator on
`test_step_by_step` in `test_mapped_task_upstream_dep.py`, replacing the terse
`# FIXME` comment with a structured explanation of:

1. **Root cause** — the test re-uses a `schedulable_tis` dict from a previous
   scheduling-decision iteration. In the `UPSTREAM_FAILED` branch, the return
   value of `_one_scheduling_decision_iteration()` is discarded (line 234 of the
   original code), so subsequent `.run()` calls on `t3` and `t4` use stale
   ORM-managed `TaskInstance` objects. Whether these stale objects are still usable
   depends on the SQLAlchemy session's identity map state, which is non-deterministic.

2. **What would fix it** — always capture the return value of
   `_one_scheduling_decision_iteration`, re-fetch TIs from the latest snapshot,
   and optionally call `session.expire_all()` between iterations.

3. **Why it stays quarantined** — the fix touches 12 parametrized combinations
   across multiple control-flow branches and interacts with scheduler internals.
   A safe fix requires careful review and testing.

## Why is this the right test layer (unit/integration/UI)?

The quarantined test is at the **unit** layer (it runs in-process with `dag_maker`),
but its flakiness stems from integration-level concerns (ORM session state across
scheduling iterations). Documenting this helps future maintainers decide whether to
fix it at the current layer or restructure it.

## What could still break / what's not covered?

- The documentation addresses only the `test_step_by_step` function. The module's
  `test_impersonation_tests.py` is also quarantined (entire module), but that requires
  the Breeze environment and is out of scope for this issue.
- The analysis is based on code reading and the linked GitHub issue; local reproduction
  of the flakiness was not performed because the test requires database fixtures.

## What risks or follow-ups remain?

- **Follow-up**: Someone should implement the suggested fix (capture return values,
  expire session) and run the 12 parametrized combinations at least 10 times locally.
- If the upstream Apache Airflow issue #38955 is resolved, this documentation should
  be updated or the quarantine marker removed.
