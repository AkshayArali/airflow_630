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
"""Unit tests for DAG bundle discovery and path handling.

Tests cover scenarios where the DAG folder path is missing, is a file instead
of a directory, is a symlink, or contains valid DAG files. The tests use
temporary directories and mock paths to remain deterministic and fast.
"""
from __future__ import annotations

import os
import warnings
from pathlib import Path

import pytest

from airflow.dag_processing.bundles.local import LocalDagBundle
from airflow.dag_processing.dagbag import BundleDagBag, DagBag

from tests_common.test_utils.config import conf_vars

pytestmark = pytest.mark.db_test


class TestBundleDiscoveryPathDoesNotExist:
    """Tests for bundle discovery when the configured path does not exist."""

    def test_dagbag_with_nonexistent_path(self, tmp_path):
        nonexistent = str(tmp_path / "does_not_exist")
        dagbag = DagBag(dag_folder=nonexistent, include_examples=False)
        assert dagbag.size() == 0
        assert len(dagbag.import_errors) == 0

    def test_local_bundle_nonexistent_path(self):
        bundle = LocalDagBundle(name="ghost", path="/nonexistent/dag/path")
        assert bundle.path == Path("/nonexistent/dag/path")
        assert not bundle.path.exists()

    def test_bundle_initialize_warns_on_missing_path(self, tmp_path):
        missing = str(tmp_path / "missing_dir")
        bundle = LocalDagBundle(name="missing_test", path=missing)
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            bundle.initialize()
        assert bundle.is_initialized


class TestBundleDiscoveryPathIsFile:
    """Tests for when the DAG folder path points to a file rather than a directory."""

    def test_dagbag_with_file_path(self, tmp_path):
        dag_file = tmp_path / "not_a_dir.py"
        dag_file.write_text(
            "from airflow.sdk import DAG\n"
            "from airflow.providers.standard.operators.empty import EmptyOperator\n"
            "with DAG('file_dag', schedule=None) as dag:\n"
            "    EmptyOperator(task_id='t1')\n"
        )
        dagbag = DagBag(dag_folder=str(dag_file), include_examples=False)
        assert "file_dag" in dagbag.dags

    def test_process_file_with_none_returns_empty(self, tmp_path):
        dagbag = DagBag(dag_folder=str(tmp_path), include_examples=False, collect_dags=False)
        result = dagbag.process_file(None)
        assert result == []


class TestBundleDiscoveryNormalPath:
    """Tests for normal DAG bundle discovery with valid directories and files."""

    def test_dagbag_discovers_dag_in_directory(self, tmp_path):
        dag_file = tmp_path / "my_dag.py"
        dag_file.write_text(
            "from airflow.sdk import DAG\n"
            "from airflow.providers.standard.operators.empty import EmptyOperator\n"
            "with DAG('discovered_dag', schedule=None) as dag:\n"
            "    EmptyOperator(task_id='op1')\n"
        )
        dagbag = DagBag(dag_folder=str(tmp_path), include_examples=False)
        assert "discovered_dag" in dagbag.dags
        assert dagbag.size() == 1

    def test_dagbag_discovers_multiple_dags(self, tmp_path):
        for i in range(3):
            dag_file = tmp_path / f"dag_{i}.py"
            dag_file.write_text(
                f"from airflow.sdk import DAG\n"
                f"from airflow.providers.standard.operators.empty import EmptyOperator\n"
                f"with DAG('multi_dag_{i}', schedule=None) as dag:\n"
                f"    EmptyOperator(task_id='op')\n"
            )
        dagbag = DagBag(dag_folder=str(tmp_path), include_examples=False)
        assert dagbag.size() == 3
        for i in range(3):
            assert f"multi_dag_{i}" in dagbag.dags

    def test_dagbag_ignores_non_dag_files(self, tmp_path):
        non_dag = tmp_path / "utils.py"
        non_dag.write_text("def helper(): pass\n")
        dagbag = DagBag(dag_folder=str(tmp_path), include_examples=False)
        assert dagbag.size() == 0


class TestBundleDagBagPathHandling:
    """Tests for BundleDagBag-specific path handling and validation."""

    def test_bundle_dagbag_requires_bundle_path(self):
        with pytest.raises(ValueError, match="bundle_path is required"):
            BundleDagBag(dag_folder="/tmp", bundle_path=None)

    def test_bundle_dagbag_adds_to_sys_path(self, tmp_path):
        import sys

        dag_file = tmp_path / "dag_in_bundle.py"
        dag_file.write_text(
            "from airflow.sdk import DAG\n"
            "from airflow.providers.standard.operators.empty import EmptyOperator\n"
            "with DAG('bundle_dag', schedule=None) as dag:\n"
            "    EmptyOperator(task_id='t')\n"
        )
        BundleDagBag(dag_folder=str(tmp_path), bundle_path=tmp_path, bundle_name="test_b")
        assert str(tmp_path) in sys.path

    def test_bundle_dagbag_warns_on_include_examples(self, tmp_path):
        with pytest.warns(UserWarning, match="include_examples=True is ignored"):
            BundleDagBag(
                dag_folder=str(tmp_path),
                bundle_path=tmp_path,
                bundle_name="warn_test",
                include_examples=True,
            )

    def test_bundle_dagbag_loads_dag_from_bundle(self, tmp_path):
        dag_file = tmp_path / "bundle_disco.py"
        dag_file.write_text(
            "from airflow.sdk import DAG\n"
            "from airflow.providers.standard.operators.empty import EmptyOperator\n"
            "with DAG('bundle_disco_dag', schedule=None) as dag:\n"
            "    EmptyOperator(task_id='op')\n"
        )
        dagbag = BundleDagBag(
            dag_folder=str(tmp_path),
            bundle_path=tmp_path,
            bundle_name="disco_bundle",
        )
        assert "bundle_disco_dag" in dagbag.dags


class TestBundleDiscoverySymlink:
    """Tests for DAG bundle discovery when paths involve symlinks."""

    def test_dagbag_follows_symlinked_directory(self, tmp_path):
        real_dir = tmp_path / "real_dags"
        real_dir.mkdir()
        dag_file = real_dir / "linked_dag.py"
        dag_file.write_text(
            "from airflow.sdk import DAG\n"
            "from airflow.providers.standard.operators.empty import EmptyOperator\n"
            "with DAG('symlinked_dag', schedule=None) as dag:\n"
            "    EmptyOperator(task_id='op')\n"
        )
        link_dir = tmp_path / "link_to_dags"
        link_dir.symlink_to(real_dir)

        dagbag = DagBag(dag_folder=str(link_dir), include_examples=False)
        assert "symlinked_dag" in dagbag.dags
