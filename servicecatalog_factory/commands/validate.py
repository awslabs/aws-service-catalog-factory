#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import os

import click

from servicecatalog_factory.utilities.assets import resolve_from_site_packages

import yamale
import logging
import yaml

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def validate(p):
    types_of_file = ["portfolios"]

    for type_of_file in types_of_file:
        target_dir = os.path.sep.join([p, type_of_file])
        if os.path.exists(target_dir):
            schema = yamale.make_schema(resolve_from_site_packages(f"schema-{type_of_file}.yaml"))
            for portfolio_file_name in os.listdir(target_dir):
                logger.info("Validating {}".format(portfolio_file_name))
                data = yamale.make_data(content=yaml.safe_dump(open(os.path.sep.join([target_dir, portfolio_file_name]), 'r').read()))
                yamale.validate(schema, data, strict=False)
                click.echo("Finished validating: {}".format(portfolio_file_name))
        click.echo("Finished validating: OK")