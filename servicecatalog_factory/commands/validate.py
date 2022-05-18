#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import os

import click

from servicecatalog_factory.utilities.assets import resolve_from_site_packages
from servicecatalog_factory.commands.extract_from_ssm import extract_from_ssm

import yamale
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def validate(p):
    extract_from_ssm(p)
    types_of_file = ["apps", "portfolios", "stacks", "workspaces"]

    for type_of_file in types_of_file:
        target_dir = os.path.sep.join([p, type_of_file])
        if os.path.exists(target_dir):
            logger.info("Validating dir: {}".format(target_dir))
            schema = yamale.make_schema(
                resolve_from_site_packages(
                    os.path.sep.join(["schema", f"schema-{type_of_file}.yaml"])
                )
            )

            portfolio_file_names = [
                i
                for i in os.listdir(target_dir)
                if os.path.isfile(os.path.sep.join([target_dir, i]))
            ]

            for portfolio_file_name in portfolio_file_names:
                logger.info("Validating file: {}".format(portfolio_file_name))
                data = yamale.make_data(
                    content=open(
                        os.path.sep.join([target_dir, portfolio_file_name]), "r"
                    ).read()
                )
                yamale.validate(schema, data, strict=False)
                click.echo("Finished validating: {}".format(portfolio_file_name))
        click.echo("Finished validating: OK")
