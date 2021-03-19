# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
from servicecatalog_factory.template_builder.cdk.product_pipeline import CDK100Template


def get(name, version):
    if name == "CDK" and version == "1.0.0":
        return CDK100Template()
    else:
        raise Exception(f"Unknown template {name}.{version} ")
