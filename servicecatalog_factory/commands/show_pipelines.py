#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import json
import os

import click
import colorclass
import terminaltables

from servicecatalog_factory import aws
from servicecatalog_factory import constants
from servicecatalog_factory.commands.portfolios import generate_portfolios


def show_pipelines(p, format):
    pipeline_names = [f"{constants.BOOTSTRAP_STACK_NAME}-pipeline"]
    for portfolio_file_name in os.listdir(p):
        if ".yaml" in portfolio_file_name:
            p_name = portfolio_file_name.split(".")[0]
            portfolios_file_path = os.path.sep.join([p, portfolio_file_name])
            portfolios = generate_portfolios(portfolios_file_path)

            for portfolio in portfolios.get("Portfolios", []):
                nested_products = portfolio.get("Products", []) + portfolio.get(
                    "Components", []
                )
                for product in nested_products:
                    for version in product.get("Versions", []):
                        pipeline_names.append(
                            f"{p_name}-{portfolio.get('DisplayName')}-{product.get('Name')}-{version.get('Name')}-pipeline"
                        )
            for product in portfolios.get("Products", []):
                for version in product.get("Versions", []):
                    pipeline_names.append(
                        f"{product.get('Name')}-{version.get('Name')}-pipeline"
                    )
    results = {}
    for pipeline_name in pipeline_names:
        result = aws.get_details_for_pipeline(pipeline_name)
        status = result.get("status")
        if status == "Succeeded":
            status = "{green}" + status + "{/green}"
        elif status == "Failed":
            status = "{red}" + status + "{/red}"
        else:
            status = "{yellow}" + status + "{/yellow}"
        if len(result.get("sourceRevisions")) > 0:
            revision = result.get("sourceRevisions")[0]
        else:
            revision = {
                "revisionId": "N/A",
                "revisionSummary": "N/A",
            }
        results[pipeline_name] = {
            "name": pipeline_name,
            "status": result.get("status"),
            "revision_id": revision.get("revisionId"),
            "revision_summary": revision.get("revisionSummary").strip(),
        }

    if format == "table":
        table_data = [
            ["Pipeline", "Status", "Last Commit Hash", "Last Commit Message"],
        ]
        for result in results.values():
            if result.get("status") == "Succeeded":
                status = f"{{green}}{result.get('status')}{{/green}}"
            elif result.get("status") == "Failed":
                status = f"{{red}}{result.get('status')}{{/red}}"
            else:
                status = f"{{yellow}}{result.get('status')}{{/yellow}}"

            table_data.append(
                [
                    result.get("name"),
                    colorclass.Color(status),
                    result.get("revision_id"),
                    result.get("revision_summary"),
                ]
            )
        table = terminaltables.AsciiTable(table_data)
        click.echo(table.table)

    elif format == "json":
        click.echo(json.dumps(results, indent=4, default=str))
