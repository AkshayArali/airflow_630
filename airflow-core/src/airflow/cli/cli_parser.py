#!/usr/bin/env python
#
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
"""
Produce a CLI parser object from Airflow CLI command configuration.

.. seealso:: :mod:`airflow.cli.cli_config`
"""

from __future__ import annotations

import argparse
import logging
import os
from argparse import Action
from collections import Counter
from collections.abc import Iterable
from functools import cache, singledispatch
from typing import TYPE_CHECKING

import lazy_object_proxy
from rich_argparse import RawTextRichHelpFormatter, RichHelpFormatter

from airflow._shared.module_loading import import_string
from airflow.cli.cli_config import (
    DAG_CLI_DICT,
    ActionCommand,
    DefaultHelpParser,
    GroupCommand,
    core_commands,
)
from airflow.cli.utils import CliConflictError
from airflow.exceptions import AirflowException
from airflow.providers_manager import ProvidersManager
from airflow.utils.helpers import partition

if TYPE_CHECKING:
    from airflow.cli.cli_config import (
        Arg,
        CLICommand,
    )

airflow_commands = core_commands.copy()  # make a copy to prevent bad interactions in tests

log = logging.getLogger(__name__)

# Expected failures while optionally loading provider/executor/auth CLI extensions.
_CLI_COMMAND_LOAD_ERRORS: tuple[type[BaseException], ...] = (
    ImportError,
    ModuleNotFoundError,
    AirflowException,
    RuntimeError,
)

_WARNING_TEMPLATE_CLI = """
Please define the 'cli' section in the 'get_provider_info' for custom {component} to avoid this warning.
For community providers, please update to the version that support 'cli' section.
For more details, see https://airflow.apache.org/docs/apache-airflow-providers/core-extensions/cli-commands.html

Providers with {component} missing 'cli' section in 'get_provider_info': {not_defined_cli_dict}
    """

_cli_extensions_loaded = False


@cache
def _providers_manager_for_cli() -> ProvidersManager:
    return ProvidersManager()


def _log_cli_extension_failure(
    source: str, detail: str, exc: BaseException, guidance: str | None = None
) -> None:
    log.exception("Failed to load CLI commands from %s: %s (%s)", source, detail, type(exc).__name__)
    log.error(guidance or "Ensure all dependencies are met and try again.")


def _load_provider_cli_extension_handlers(commands: list[CLICommand]) -> None:
    providers_manager = _providers_manager_for_cli()
    try:
        for cli_function in providers_manager.cli_command_functions:
            try:
                commands.extend(cli_function())
            except _CLI_COMMAND_LOAD_ERRORS as exc:
                _log_cli_extension_failure("provider function", cli_function.__name__, exc)
    except _CLI_COMMAND_LOAD_ERRORS as e:
        log.warning(
            "Failed to load CLI commands from providers (%s): %s",
            type(e).__name__,
            e,
        )


def _load_executor_compat_cli_extensions(commands: list[CLICommand]) -> None:
    providers_manager = _providers_manager_for_cli()
    try:
        executors_not_defined_cli = {
            executor_name: executor_provider
            for executor_name, executor_provider in providers_manager.executor_without_check
            if executor_provider not in providers_manager.cli_command_providers
        }
        if executors_not_defined_cli:
            log.warning(
                _WARNING_TEMPLATE_CLI.format(
                    component="executors", not_defined_cli_dict=str(executors_not_defined_cli)
                )
            )
            from airflow.executors.executor_loader import ExecutorLoader

            for executor_name in ExecutorLoader.get_executor_names(validate_teams=False):
                if executor_name.module_path not in executors_not_defined_cli:
                    log.debug(
                        "Skipping loading for '%s' as it is defined in 'cli' section.",
                        executor_name.module_path,
                    )
                    continue

                try:
                    executor, _ = ExecutorLoader.import_executor_cls(executor_name)
                    commands.extend(executor.get_cli_commands())
                except _CLI_COMMAND_LOAD_ERRORS as exc:
                    _log_cli_extension_failure(
                        "executor",
                        str(executor_name),
                        exc,
                        guidance=(
                            "Ensure all dependencies are met and try again. If using a Celery based executor install "
                            "a 3.3.0+ version of the Celery provider. If using a Kubernetes executor, install a "
                            "7.4.0+ version of the CNCF provider"
                        ),
                    )
    except _CLI_COMMAND_LOAD_ERRORS as e:
        log.warning(
            "Failed to load CLI commands from executors that didn't define `get_cli_commands` in `.cli.definition` (%s): %s",
            type(e).__name__,
            e,
        )


def _load_auth_manager_compat_cli_extensions(commands: list[CLICommand]) -> None:
    providers_manager = _providers_manager_for_cli()
    try:
        auth_managers_not_defined_cli = {
            auth_manager_name: auth_manager_provider
            for auth_manager_name, auth_manager_provider in providers_manager.auth_manager_without_check
            if auth_manager_provider not in providers_manager.cli_command_providers
        }
        if auth_managers_not_defined_cli:
            log.warning(
                _WARNING_TEMPLATE_CLI.format(
                    component="auth manager", not_defined_cli_dict=str(auth_managers_not_defined_cli)
                )
            )

            from airflow.configuration import conf
            from airflow.exceptions import AirflowConfigException

            auth_manager_cls_path = conf.get(section="core", key="auth_manager")

            if not auth_manager_cls_path:
                raise AirflowConfigException(
                    "No auth manager defined in the config. Please specify one using section/key [core/auth_manager]."
                )

            if auth_manager_cls_path in auth_managers_not_defined_cli:
                try:
                    auth_manager_cls = import_string(auth_manager_cls_path)
                    auth_manager = auth_manager_cls()
                    commands.extend(auth_manager.get_cli_commands())
                except _CLI_COMMAND_LOAD_ERRORS as exc:
                    _log_cli_extension_failure("auth manager", auth_manager_cls_path, exc)
    except _CLI_COMMAND_LOAD_ERRORS as e:
        log.warning(
            "Failed to load CLI commands from auth managers that didn't define `get_cli_commands` in `.cli.definition` (%s): %s",
            type(e).__name__,
            e,
        )


def _cli_extension_chain(commands: list[CLICommand]) -> None:
    """Chain of Responsibility: optional CLI sources applied in fixed order."""
    for handler in (
        _load_provider_cli_extension_handlers,
        _load_executor_compat_cli_extensions,
        _load_auth_manager_compat_cli_extensions,
    ):
        handler(commands)


def _validate_cli_command_uniqueness(commands: list[CLICommand]) -> None:
    all_commands_dict = {sp.name: sp for sp in commands}
    if len(all_commands_dict) < len(commands):
        dup = {k for k, v in Counter([c.name for c in commands]).items() if v > 1}
        raise CliConflictError(
            f"The following CLI {len(dup)} command(s) are defined more than once: {sorted(dup)}\n"
            f"This can be due to a Provider redefining core airflow CLI commands."
        )


def ensure_cli_commands_loaded() -> None:
    """
    Lazy-load provider/executor/auth manager CLI extensions (virtual proxy).

    Importing this module only registers core commands; extensions load when the CLI is built.
    """
    global _cli_extensions_loaded
    if _cli_extensions_loaded:
        return
    # AIRFLOW_PACKAGE_NAME is set when generating docs — skip optional extensions (same as before).
    if not os.environ.get("AIRFLOW_PACKAGE_NAME", None):
        _cli_extension_chain(airflow_commands)
    _validate_cli_command_uniqueness(airflow_commands)
    _cli_extensions_loaded = True


def get_all_commands_dict() -> dict[str, CLICommand]:
    """Resolved command map (lazy: triggers extension loading on first use)."""
    ensure_cli_commands_loaded()
    return {sp.name: sp for sp in airflow_commands}


class AirflowHelpFormatter(RichHelpFormatter):
    """
    Custom help formatter to display help message.

    It displays simple commands and groups of commands in separate sections.
    """

    def _iter_indented_subactions(self, action: Action):
        if isinstance(action, argparse._SubParsersAction):
            self._indent()
            subactions = action._get_subactions()
            action_subcommands, group_subcommands = partition(
                lambda d: isinstance(get_all_commands_dict()[d.dest], GroupCommand), subactions
            )
            yield Action([], f"\n{' ':{self._current_indent}}Groups", nargs=0)
            self._indent()
            yield from group_subcommands
            self._dedent()

            yield Action([], f"\n{' ':{self._current_indent}}Commands:", nargs=0)
            self._indent()
            yield from action_subcommands
            self._dedent()
            self._dedent()
        else:
            yield from super()._iter_indented_subactions(action)


class LazyRichHelpFormatter(RawTextRichHelpFormatter):
    """
    Custom help formatter to display help message.

    It resolves lazy help string before printing it using rich.
    """

    def add_argument(self, action: Action) -> None:
        if isinstance(action.help, lazy_object_proxy.Proxy):
            action.help = str(action.help)
        return super().add_argument(action)


@cache
def get_parser(dag_parser: bool = False) -> argparse.ArgumentParser:
    """Create and returns command line argument parser."""
    parser = DefaultHelpParser(prog="airflow", formatter_class=AirflowHelpFormatter)
    subparsers = parser.add_subparsers(dest="subcommand", metavar="GROUP_OR_COMMAND")
    subparsers.required = True

    command_dict = DAG_CLI_DICT if dag_parser else get_all_commands_dict()
    for _, sub in sorted(command_dict.items()):
        _add_command(subparsers, sub)
    return parser


def _sort_args(args: Iterable[Arg]) -> Iterable[Arg]:
    """Sort subcommand optional args, keep positional args."""

    def get_long_option(arg: Arg):
        """Get long option from Arg.flags."""
        return arg.flags[0] if len(arg.flags) == 1 else arg.flags[1]

    positional, optional = partition(lambda x: x.flags[0].startswith("-"), args)
    yield from positional
    yield from sorted(optional, key=lambda x: get_long_option(x).lower())


@singledispatch
def _configure_command(sub: object, sub_proc: argparse.ArgumentParser) -> None:
    raise AirflowException("Invalid command definition.")


@_configure_command.register(ActionCommand)
def _(sub: ActionCommand, sub_proc: argparse.ArgumentParser) -> None:
    for arg in _sort_args(sub.args):
        arg.add_to_parser(sub_proc)
    sub_proc.set_defaults(func=sub.func)


@_configure_command.register(GroupCommand)
def _(sub: GroupCommand, sub_proc: argparse.ArgumentParser) -> None:
    sub_subparsers = sub_proc.add_subparsers(dest="subcommand", metavar="COMMAND")
    sub_subparsers.required = True
    for command in sorted(sub.subcommands, key=lambda x: x.name):
        _add_command(sub_subparsers, command)


def _add_command(subparsers: argparse._SubParsersAction, sub: CLICommand) -> None:
    if isinstance(sub, ActionCommand) and sub.hide:
        sub_proc = subparsers.add_parser(sub.name, epilog=sub.epilog)
    else:
        sub_proc = subparsers.add_parser(
            sub.name, help=sub.help, description=sub.description or sub.help, epilog=sub.epilog
        )
    sub_proc.formatter_class = LazyRichHelpFormatter
    _configure_command(sub, sub_proc)
