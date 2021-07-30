# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import glob
import os
import yaml
from threading import Thread

import click
from betterboto import client as betterboto_client

from servicecatalog_factory import constants
from servicecatalog_factory.commands.portfolios import get_regions
from servicecatalog_factory.workflow.stacks import create_stack_version_pipeline_task
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
                kwargs={
                    "stack_name": stack_name,
                    "region": region,
                },
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


def generate(stacks_path, factory_version):
    tasks = list()
    for stack_file_name in glob.glob(f"{stacks_path}/*.yaml"):
        stack_file = yaml.safe_load(open(stack_file_name, 'r').read())
        for stack in stack_file.get("Stacks", []):
            for version in stack.get("Versions", []):
                stages = always_merger.merge(
                    stack.get("Stages", {}), version.get("Stages", {})
                )
                # if stages.get("Package") is None:
                #     stages["Package"] = dict(
                #         BuildSpecImage=version.get(
                #             "BuildSpecImage",
                #             stack.get(
                #                 "BuildSpecImage",
                #                 constants.PACKAGE_BUILD_SPEC_IMAGE_DEFAULT,
                #             ),
                #         ),
                #         BuildSpec=version.get(
                #             "BuildSpec",
                #             stack.get("BuildSpec", constants.PACKAGE_BUILD_SPEC_DEFAULT),
                #         ),
                #     )

                tasks.append(
                    create_stack_version_pipeline_task.CreateStackVersionPipelineTask(
                        name=stack.get("Name"),
                        version=version.get("Name"),
                        source=always_merger.merge(
                            stack.get("Source", {}), version.get("Source", {})
                        ),
                        options=always_merger.merge(
                            stack.get("Options", {}), version.get("Options", {})
                        ),
                        stages=stages,
                    )
                )

    return tasks
