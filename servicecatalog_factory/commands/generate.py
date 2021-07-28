# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
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

from servicecatalog_factory import constants
from servicecatalog_factory.commands.portfolios import (
    get_regions,
    generate_portfolios,
    generate_for_portfolios,
    generate_for_products,
    generate_for_portfolios_versions,
    generate_for_products_versions,
)
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def generate_via_luigi(p):
    # factory_version = (
    #     constants.VERSION
    #     if branch_override is None
    #     else "https://github.com/awslabs/aws-service-catalog-factory/archive/{}.zip".format(
    #         branch_override
    #     )
    # )
    factory_version = constants.VERSION
    logger.info("Generating")
    all_tasks = {}
    all_regions = get_regions()
    products_by_region = {}
    pipeline_versions = list()
    products_versions = dict()

    for portfolio_file_name in os.listdir(p):
        if ".yaml" in portfolio_file_name:
            p_name = portfolio_file_name.split(".")[0]
            portfolios_file_path = os.path.sep.join([p, portfolio_file_name])
            portfolios = generate_portfolios(portfolios_file_path)
            for region in all_regions:
                generate_for_portfolios(
                    all_tasks,
                    factory_version,
                    p_name,
                    portfolios,
                    products_by_region,
                    region,
                    pipeline_versions,
                )
                generate_for_products(
                    all_tasks,
                    p_name,
                    portfolios,
                    products_by_region,
                    region,
                    products_versions,
                )

    logger.info("Going to create pipeline tasks")
    generate_for_portfolios_versions(
        all_regions,
        all_tasks,
        factory_version,
        pipeline_versions,
        products_by_region,
    )
    generate_for_products_versions(
        all_regions,
        all_tasks,
        factory_version,
        products_versions,
        products_by_region,
    )

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
        all_tasks.values(),
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
