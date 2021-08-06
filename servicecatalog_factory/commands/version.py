#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import click
from betterboto import client as betterboto_client

from servicecatalog_factory import config
from servicecatalog_factory import constants


def version():
    click.echo("cli version: {}".format(constants.VERSION))
    with betterboto_client.ClientContextManager(
        "ssm", region_name=constants.HOME_REGION
    ) as ssm:
        response = ssm.get_parameter(Name="service-catalog-factory-regional-version")
        click.echo(
            "regional stack version: {} for region: {}".format(
                response.get("Parameter").get("Value"),
                response.get("Parameter").get("ARN").split(":")[3],
            )
        )
        response = config.get_stack_version()
        click.echo("stack version: {}".format(response))
