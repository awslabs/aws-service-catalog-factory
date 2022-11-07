#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import json
import os
import shutil
import sys
from glob import glob
from pathlib import Path

import click
import colorclass
import luigi
import terminaltables
import yaml
from luigi import LuigiStatusCode

from servicecatalog_factory.common import serialisation_utils, utils
from servicecatalog_factory.commands import portfolios as portfolios_commands
from servicecatalog_factory.commands import task_reference as task_reference_commands
from servicecatalog_factory import constants, config
from servicecatalog_factory.commands.extract_from_ssm import extract_from_ssm

from servicecatalog_factory.waluigi import scheduler

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


TASK_REFERENCE_JSON_FILE_PATH = "task-reference.json"


def generate(p):
    factory_version = constants.VERSION

    logger.info("Generating")

    extract_from_ssm(p)
    enabled_regions = config.get_regions()

    task_reference = task_reference_commands.generate_task_reference(
        p, enabled_regions, factory_version
    )

    open(f"{p}/{TASK_REFERENCE_JSON_FILE_PATH}", "w").write(
        json.dumps(task_reference, indent=4)
    )

    if not os.path.exists(f"{p}/tasks"):
        os.makedirs(f"{p}/tasks")
    for t_name, task in task_reference.items():
        task_output_file_path = f"{p}/tasks/{utils.escape(t_name)}.json"
        task_output_content = serialisation_utils.dump_as_json(task)
        open(task_output_file_path, "w").write(task_output_content)

    for type in [
        "start",
        "failure",
        "success",
        "timeout",
        "process_failure",
        "processing_time",
        "broken_task",
    ]:
        os.makedirs(Path(constants.RESULTS_DIRECTORY) / type)

    os.environ["SCT_SHOULD_PIPELINES_INHERIT_TAGS"] = str(
        config.get_should_pipelines_inherit_tags()
    )
    os.environ["SCT_INITIALISER_STACK_TAGS"] = json.dumps(
        config.get_initialiser_stack_tags()
    )

    scheduler.run(
        num_workers=10,
        tasks_to_run=task_reference,
        manifest_files_path=p,
        manifest_task_reference_file_path=f"{p}/{TASK_REFERENCE_JSON_FILE_PATH}",
        puppet_account_id="012345678910",
    )

    table_data = [
        ["Result", "Task", "Significant Parameters", "Duration"],
    ]
    table = terminaltables.AsciiTable(table_data)
    for filename in glob("results/success/*.json"):
        result = json.loads(open(filename, "r").read())
        table_data.append(
            [
                colorclass.Color("{green}Success{/green}"),
                result.get("task_type"),
                yaml.safe_dump(result.get("params_for_results")),
                result.get("duration"),
            ]
        )
    for filename in glob("results/failure/*.json"):
        result = json.loads(open(filename, "r").read())
        table_data.append(
            [
                colorclass.Color("{red}Failure{/red}"),
                result.get("task_type"),
                yaml.safe_dump(result.get("params_for_results")),
                result.get("duration"),
            ]
        )
    click.echo(table.table)

    has_failure = False
    for filename in glob("results/failure/*.json"):
        has_failure = True
        result = json.loads(open(filename, "r").read())
        click.echo(
            colorclass.Color("{red}" + result.get("task_type") + " failed{/red}")
        )
        click.echo(f"{yaml.safe_dump({'parameters': result.get('task_params')})}")
        click.echo("\n".join(result.get("exception_stack_trace")))
        click.echo("")

    sys.exit(1 if has_failure else 0)
