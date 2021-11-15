#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import glob
import os
import yaml
from threading import Thread

import click
from betterboto import client as betterboto_client

from servicecatalog_factory import constants
from servicecatalog_factory.commands.portfolios import get_regions
from servicecatalog_factory.workflow.generic import create_generic_version_pipeline_task
from deepmerge import always_merger


def delete_stack_from_all_regions(stack_name):
    all_regions = get_regions()
    if click.confirm(
        "We are going to delete the stack: {} from all regions: {}.  Are you sure?".format(
            stack_name, all_regions
        )
    ):
        threads = []
        for region in all_regions:
            process = Thread(
                name=region,
                target=delete_stack_from_a_regions,
                kwargs={"stack_name": stack_name, "region": region,},
            )
            process.start()
            threads.append(process)
        for process in threads:
            process.join()


def delete_stack_from_a_regions(stack_name, region):
    click.echo("Deleting stack: {} from region: {}".format(stack_name, region))
    with betterboto_client.ClientContextManager(
        "cloudformation", region_name=region
    ) as cloudformation:
        cloudformation.delete_stack(StackName=stack_name)
        waiter = cloudformation.get_waiter("stack_delete_complete")
        waiter.wait(StackName=stack_name)
    click.echo("Finished")
