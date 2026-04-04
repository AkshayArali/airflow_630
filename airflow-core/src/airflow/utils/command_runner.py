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
"""Utilities for running shell commands and capturing stdout."""

from __future__ import annotations

import shlex
import subprocess
import sys

from airflow.exceptions import AirflowConfigException


def run_command(command: str) -> str:
    """Run command and returns stdout."""
    process = subprocess.Popen(
        shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True
    )
    output, stderr = (stream.decode(sys.getdefaultencoding(), "ignore") for stream in process.communicate())

    if process.returncode != 0:
        raise AirflowConfigException(
            f"Cannot execute {command}. Error code is: {process.returncode}. "
            f"Output: {output}, Stderr: {stderr}"
        )

    return output

