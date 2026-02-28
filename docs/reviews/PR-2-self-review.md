# PR-2 Self-Review: Shared fixture for minimal DAG bag

## What I changed and why

I added a reusable `minimal_dagbag` pytest fixture in `airflow-core/tests/conftest.py`. It creates a temp directory with one no-op DAG file and returns a `DagBag` so tests don’t have to repeat that setup.

I also added `test_minimal_dagbag_fixture.py` with 7 tests that check the fixture (DAG count, expected task, no import errors, etc.). Those tests both guard the fixture and show how to use it.

## Why unit tests

The fixture builds an in-memory DagBag from a temp file. No Airflow server, DB, or network—just unit-level tests.

## What I didn’t cover / limitations

- The fixture always uses `schedule=None`. If a test needs a scheduled DAG, it’ll need its own setup or we could add a parametrized variant later.
- It uses `EmptyOperator` from `airflow.providers.standard`, so the standard provider has to be installed.

## Follow-ups

- If `EmptyOperator` moves to another package, the fixture’s DAG file will need an update.
- We could add a `minimal_dagbag_factory` that takes options (number of DAGs, tasks, schedule) for more flexibility.
- Other tests that build one-off DagBags with a single DAG could be migrated to this fixture over time.
