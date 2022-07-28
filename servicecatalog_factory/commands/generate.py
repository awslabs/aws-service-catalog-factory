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

from servicecatalog_factory.commands import portfolios as portfolios_commands
from servicecatalog_factory.commands import generic as generic_commands
from servicecatalog_factory import constants, config
from servicecatalog_factory.commands.extract_from_ssm import extract_from_ssm

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def rewrite_products(p):
    portfolios_for_reference = dict()

    for portfolio_yaml_file in glob(f"{p}/portfolios/*.yaml"):
        logger.info(f"Processing (for get portfolios): {portfolio_yaml_file}")
        p_name = Path(portfolio_yaml_file).stem
        portfolio_yaml = portfolios_commands.generate_portfolios(portfolio_yaml_file)
        for portfolio in portfolio_yaml.get("Portfolios", []):
            portfolio["PortfolioGroupName"] = p_name
            if portfolio.get("Products"):
                del portfolio["Products"]
            if portfolio.get("DisplayName"):
                portfolios_for_reference[
                    f"{p_name}-{portfolio.get('DisplayName')}"
                ] = portfolio
            elif portfolio.get("PortfolioName"):
                portfolios_for_reference[portfolio.get("PortfolioName")] = portfolio
            else:
                raise Exception(
                    f"portfolio must have DisplayName of PortfolioName: {portfolio}"
                )
    logger.info(f"Finished building reference")

    # get the products out of the portfolios
    products_to_move = list()
    for portfolio_yaml_file in glob(f"{p}/portfolios/*.yaml"):
        logger.info(f"Processing (for get products): {portfolio_yaml_file}")
        p_name = Path(portfolio_yaml_file).stem
        portfolio_yaml = portfolios_commands.generate_portfolios(portfolio_yaml_file)
        for product in portfolio_yaml.get("Products", []) + portfolio_yaml.get(
            "Components", []
        ):
            new_portfolios = list()
            for portfolio in product.get("Portfolios", []):
                new_portfolios.append(f"{p_name}-{portfolio}")
            products_to_move.append(product)

        for portfolio in portfolio_yaml.get("Portfolios", []):
            for product in portfolio.get("Products", []) + portfolio.get(
                "Components", []
            ):
                if portfolio.get("PortfolioName"):
                    portfolio_name = portfolio.get("PortfolioName")
                else:
                    portfolio_name = f"{p_name}-{portfolio.get('DisplayName')}"
                product["Portfolios"] = [portfolio_name]
                products_to_move.append(product)
    logger.info(f"Finished getting products from portfolios/")

    # write the new products file
    products_path = f"{p}/products"
    if not os.path.exists(products_path):
        os.makedirs(products_path)
    open(f"{products_path}/_imported.yaml", "w").write(
        yaml.safe_dump(dict(Products=products_to_move))
    )
    logger.info(f"Finished moving")

    # remove the products from the portfolios
    for portfolio_yaml_file in glob(f"{p}/portfolios/*.yaml"):
        logger.info(f"Processing (for removing products): {portfolio_yaml_file}")
        p_name = Path(portfolio_yaml_file).stem
        portfolio_yaml_file_content = open(portfolio_yaml_file, "r").read()
        portfolio_yaml = yaml.safe_load(portfolio_yaml_file_content)
        if portfolio_yaml.get("Products"):
            del portfolio_yaml["Products"]
        if portfolio_yaml.get("Components"):
            del portfolio_yaml["Components"]

        for portfolio in portfolio_yaml.get("Portfolios", []):
            if portfolio.get("Products"):
                del portfolio["Products"]
            if portfolio.get("Components"):
                del portfolio["Components"]
            external_portfolio_definition_path = f"{p}/portfolios/{p_name}/{portfolio.get('DisplayName', portfolio.get('PortfolioName'))}"
            if os.path.exists(external_portfolio_definition_path):
                shutil.rmtree(external_portfolio_definition_path)
        open(portfolio_yaml_file, "w").write(yaml.safe_dump(portfolio_yaml))
    logger.info(f"Finished removing products from portfolios/")

    # rewrite portfolios in the product
    for product_yaml_file in glob(f"{p}/products/*"):
        logger.info(f"Processing (for rewrite): {product_yaml_file}")
        product_yaml_file_content = open(product_yaml_file, "r").read()
        product_yaml = yaml.safe_load(product_yaml_file_content)
        for product in product_yaml.get("Products", []):
            new_portfolios = list()
            for portfolio in product.get("Portfolios", []):
                if isinstance(portfolio, str) and portfolios_for_reference.get(
                    portfolio
                ):
                    new_portfolios.append(portfolios_for_reference.get(portfolio))
                else:
                    new_portfolios.append(portfolio)
            product["Portfolios"] = new_portfolios
        open(product_yaml_file, "w").write(yaml.safe_dump(product_yaml))


def rewrite(p):
    rewrite_products(p)


def generate(p):
    factory_version = constants.VERSION

    logger.info("Generating")
    tasks = []

    extract_from_ssm(p)
    rewrite(p)
    portfolios_path = os.path.sep.join([p, "portfolios"])
    portfolio_tasks = portfolios_commands.generate(portfolios_path, factory_version)
    for k, v in portfolio_tasks.items():
        if isinstance(v, dict):
            tasks += list(v.values())
        else:
            tasks.append(v)

    products_path = os.path.sep.join([p, "products"])
    product_tasks = generic_commands.generate(
        products_path, "Products", "products", factory_version
    )
    tasks.extend(product_tasks)

    stacks_path = os.path.sep.join([p, "stacks"])
    tasks += generic_commands.generate(stacks_path, "Stacks", "stack", factory_version)

    workspaces_path = os.path.sep.join([p, "workspaces"])
    tasks += generic_commands.generate(
        workspaces_path, "Workspaces", "workspace", factory_version
    )

    apps_path = os.path.sep.join([p, "apps"])
    tasks += generic_commands.generate(apps_path, "Apps", "app", factory_version)

    for type in [
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
