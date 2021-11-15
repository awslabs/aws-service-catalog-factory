#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
from servicecatalog_factory.template_builder.cdk.product_pipeline import CDK100Template
from servicecatalog_factory.template_builder import builders


def get(name, version):
    if name == "CDK" and version == "1.0.0":
        return CDK100Template()
    else:
        raise Exception(f"Unknown template {name}.{version} ")


def get_v2(name):
    if name == "stack":
        return builders.StackTemplateBuilder()
    elif name == "workspace":
        return builders.TerraformTemplateBuilder()
    elif name == "app":
        return builders.CDKAppTemplateBuilder()
    else:
        raise Exception(f"Unsupported: {name}")
