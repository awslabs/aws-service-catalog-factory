#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import os

import yaml
from betterboto import client as betterboto_client
from servicecatalog_factory import constants, environmental_variables
import functools
import logging

logger = logging.getLogger(__file__)


def get_stack_version():
    with betterboto_client.ClientContextManager(
        "ssm", region_name=constants.HOME_REGION
    ) as ssm:
        return (
            ssm.get_parameter(Name="service-catalog-factory-version")
            .get("Parameter")
            .get("Value")
        )


@functools.lru_cache(maxsize=32)
def get_regions():
    with betterboto_client.ClientContextManager(
        "ssm", region_name=constants.HOME_REGION
    ) as ssm:
        response = ssm.get_parameter(Name=constants.CONFIG_PARAM_NAME)
        config = yaml.safe_load(response.get("Parameter").get("Value"))
        return config.get("regions")


@functools.lru_cache(maxsize=32)
def get_initialiser_stack_tags():
    with betterboto_client.ClientContextManager("ssm") as ssm:
        try:
            response = ssm.get_parameter(
                Name=constants.INITIALISER_STACK_NAME_SSM_PARAMETER
            )
            initialiser_stack_name = response.get("Parameter").get("Value")
            with betterboto_client.ClientContextManager(
                "cloudformation"
            ) as cloudformation:
                paginator = cloudformation.get_paginator("describe_stacks")
                for page in paginator.paginate(StackName=initialiser_stack_name,):
                    for stack in page.get("Stacks", []):
                        if stack.get("StackStatus") in [
                            "CREATE_IN_PROGRESS",
                            "CREATE_COMPLETE",
                            "UPDATE_IN_PROGRESS",
                            "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
                            "UPDATE_COMPLETE",
                        ]:
                            return stack.get("Tags")
                        else:
                            raise Exception(
                                f"Initialiser stack: {initialiser_stack_name} in state: {stack.get('StackStatus')}"
                            )
        except ssm.exceptions.ParameterNotFound:
            logger.warning(
                f"Could not find SSM parameter: {constants.INITIALISER_STACK_NAME_SSM_PARAMETER}, do not know the tags to use"
            )
            return []


def get_config():
    logger.info("getting config")
    with betterboto_client.ClientContextManager("ssm",) as ssm:
        response = ssm.get_parameter(Name=constants.CONFIG_PARAM_NAME)
        return yaml.safe_load(response.get("Parameter").get("Value"))


@functools.lru_cache(maxsize=32)
def get_should_pipelines_inherit_tags():
    logger.info(f"getting {constants.CONFIG_SHOULD_PIPELINES_INHERIT_TAGS}")
    return get_config().get(constants.CONFIG_SHOULD_PIPELINES_INHERIT_TAGS, True)


def get_aws_url_suffix():
    return os.getenv(
        environmental_variables.AWS_URL_SUFFIX, constants.AWS_URL_SUFFIX_DEFAULT
    )
