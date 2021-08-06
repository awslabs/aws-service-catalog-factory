#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import os

import click
from pykwalify.core import Core

from servicecatalog_factory.utilities.assets import resolve_from_site_packages

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def validate(p):
    for portfolio_file_name in os.listdir(p):
        portfolios_file_path = os.path.sep.join([p, portfolio_file_name])
        logger.info("Validating {}".format(portfolios_file_path))
        core = Core(
            source_file=portfolios_file_path,
            schema_files=[resolve_from_site_packages("schema.yaml")],
        )
        core.validate(raise_exception=True)
        click.echo("Finished validating: {}".format(portfolios_file_path))
    click.echo("Finished validating: OK")
