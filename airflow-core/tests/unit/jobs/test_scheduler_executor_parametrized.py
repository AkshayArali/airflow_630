# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Parametrized scheduler tests across multiple executor backend types.

These tests verify that core scheduler-executor interactions (start, heartbeat,
event buffer, job ID assignment) behave consistently regardless of which
executor backend is configured. Each test is parametrized over at least two
executor types to catch backend-specific regressions.
"""
from __future__ import annotations

import os
from unittest import mock
from unittest.mock import MagicMock, PropertyMock

import pytest

from airflow.api_fastapi.auth.tokens import JWTGenerator
from airflow.executors.base_executor import BaseExecutor
from airflow.executors.executor_utils import ExecutorName
from airflow.jobs.job import Job
from airflow.jobs.scheduler_job_runner import SchedulerJobRunner

pytestmark = pytest.mark.db_test


EXECUTOR_BACKENDS = [
    pytest.param(
        "local_exec",
        "airflow.executors.local_executor.LocalExecutor",
        id="LocalExecutor",
    ),
    pytest.param(
        "celery_exec",
        "airflow.providers.celery.executors.celery_executor.CeleryExecutor",
        id="CeleryExecutor",
    ),
]


@pytest.fixture(params=EXECUTOR_BACKENDS)
def mock_executor_backend(request):
    """Provide a mock executor configured with the given alias and module path."""
    alias, module_path = request.param
    mock_jwt = MagicMock(spec=JWTGenerator)
    mock_jwt.generate.return_value = "mock-token"

    executor = mock.MagicMock(
        name=f"Mock-{alias}",
        slots_available=8,
        slots_occupied=0,
    )
    executor.name = ExecutorName(alias=alias, module_path=module_path)
    executor.jwt_generator = mock_jwt
    executor.team_name = None
    executor.sentry_integration = ""
    executor.queue_workload.__func__ = BaseExecutor.queue_workload

    with mock.patch("airflow.jobs.job.Job.executors", new_callable=PropertyMock) as executors_mock:
        executors_mock.return_value = [executor]
        yield executor


class TestSchedulerExecutorParametrized:
    """Verify scheduler-executor lifecycle methods across different executor backends."""

    @pytest.fixture(autouse=True)
    def _init(self):
        self.job_runner: SchedulerJobRunner | None = None
        yield

    def test_executor_start_called(self, mock_executor_backend):
        """Scheduler must call executor.start() exactly once during _execute."""
        scheduler_job = Job()
        self.job_runner = SchedulerJobRunner(job=scheduler_job, num_runs=1)
        self.job_runner._execute()

        mock_executor_backend.start.assert_called_once()

    def test_executor_job_id_assigned(self, mock_executor_backend, configure_testing_dag_bundle):
        """Scheduler must assign its own job ID to each executor."""
        with configure_testing_dag_bundle(os.devnull):
            scheduler_job = Job()
            self.job_runner = SchedulerJobRunner(job=scheduler_job, num_runs=1)
            self.job_runner._execute()

            assert mock_executor_backend.job_id == scheduler_job.id

    def test_executor_heartbeat_called(self, mock_executor_backend, configure_testing_dag_bundle):
        """Scheduler must call executor.heartbeat() at least once per run."""
        with configure_testing_dag_bundle(os.devnull):
            scheduler_job = Job()
            self.job_runner = SchedulerJobRunner(job=scheduler_job, num_runs=1)
            self.job_runner._execute()

            mock_executor_backend.heartbeat.assert_called_once()

    def test_executor_event_buffer_read(self, mock_executor_backend, configure_testing_dag_bundle):
        """Scheduler must read the event buffer from the executor during its loop."""
        with configure_testing_dag_bundle(os.devnull):
            scheduler_job = Job()
            self.job_runner = SchedulerJobRunner(job=scheduler_job, num_runs=1)
            self.job_runner._execute()

            mock_executor_backend.get_event_buffer.assert_called_once()

    def test_executor_end_called(self, mock_executor_backend):
        """Scheduler must call executor.end() when shutting down."""
        scheduler_job = Job()
        self.job_runner = SchedulerJobRunner(job=scheduler_job, num_runs=1)
        self.job_runner._execute()

        mock_executor_backend.end.assert_called_once()

    def test_executor_slots_available_respected(self, mock_executor_backend):
        """Verify the scheduler sees executor slot counts correctly."""
        assert mock_executor_backend.slots_available == 8
        assert mock_executor_backend.slots_occupied == 0
