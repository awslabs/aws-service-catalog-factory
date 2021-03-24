# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import troposphere as t

from servicecatalog_factory.template_builder import shared_resources
from servicecatalog_factory.template_builder.cdk import (
    shared_resources as cdk_shared_resources,
)


def get_template() -> t.Template:
    description = "Shared resources used by product pipelines"
    tpl = t.Template(Description=description)

    for resource in (
        shared_resources.get_resources() + cdk_shared_resources.get_resources()
    ):
        tpl.add_resource(resource)

    return tpl
