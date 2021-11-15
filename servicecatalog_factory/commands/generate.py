#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import json
import os
import sys
from glob import glob
from pathlib import Path

import click
import colorclass
import luigi
import terminaltables
import yaml
from luigi import LuigiStatusCode

from servicecatalog_factory.commands import portfolios as portfolios_commands
from servicecatalog_factory.commands import generic as generic_commands
from servicecatalog_factory import constants

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def generate(p):
    factory_version = constants.VERSION
    logger.info("Generating")
    tasks = []

    portfolios_path = os.path.sep.join([p, "portfolios"])
    tasks += portfolios_commands.generate(portfolios_path, factory_version)

    stacks_path = os.path.sep.join([p, "stacks"])
    tasks += generic_commands.generate(stacks_path, "Stacks", "stack", factory_version)

    workspaces_path = os.path.sep.join([p, "workspaces"])
    tasks += generic_commands.generate(
        workspaces_path, "Workspaces", "workspace", factory_version
    )

    workspaces_path = os.path.sep.join([p, "apps"])
    tasks += generic_commands.generate(workspaces_path, "Apps", "app", factory_version)

    for type in [
        "failure",
        "success",
        "timeout",
        "process_failure",
        "processing_time",
        "broken_task",
    ]:
        os.makedirs(Path(constants.RESULTS_DIRECTORY) / type)

    run_result = luigi.build(
        tasks,
        local_scheduler=True,
        detailed_summary=True,
        workers=10,
        log_level="INFO",
    )

    exit_status_codes = {
        LuigiStatusCode.SUCCESS: 0,
        LuigiStatusCode.SUCCESS_WITH_RETRY: 0,
        LuigiStatusCode.FAILED: 1,
        LuigiStatusCode.FAILED_AND_SCHEDULING_FAILED: 2,
        LuigiStatusCode.SCHEDULING_FAILED: 3,
        LuigiStatusCode.NOT_RUN: 4,
        LuigiStatusCode.MISSING_EXT: 5,
    }

    table_data = [
        ["Result", "Task", "Significant Parameters", "Duration"],
    ]
    table = terminaltables.AsciiTable(table_data)
    for filename in glob("results/processing_time/*.json"):
        result = json.loads(open(filename, "r").read())
        table_data.append(
            [
                colorclass.Color("{green}Success{/green}"),
                result.get("task_type"),
                yaml.safe_dump(result.get("params_for_results")),
                result.get("duration"),
            ]
        )
    click.echo(table.table)

    for filename in glob("results/failure/*.json"):
        result = json.loads(open(filename, "r").read())
        click.echo(
            colorclass.Color("{red}" + result.get("task_type") + " failed{/red}")
        )
        click.echo(f"{yaml.safe_dump({'parameters': result.get('task_params')})}")
        click.echo("\n".join(result.get("exception_stack_trace")))
        click.echo("")

    sys.exit(exit_status_codes.get(run_result.status))
