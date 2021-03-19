# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import troposphere as t

from servicecatalog_factory.template_builder import shared_resources
from servicecatalog_factory.template_builder.cdk import (
    shared_resources as cdk_shared_resources,
)


def get_template() -> t.Template:
    description = "todo"
    tpl = t.Template(Description=description)

    for resource in shared_resources.resources + cdk_shared_resources.resources:
        tpl.add_resource(resource)

    return tpl
