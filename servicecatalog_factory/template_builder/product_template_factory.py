#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
from servicecatalog_factory.template_builder.cdk.product_pipeline import CDK100Template
from servicecatalog_factory.template_builder import builders_noncfn
from servicecatalog_factory.template_builder import builders_cfn
from servicecatalog_factory.template_builder import builders_cfn_combined
from servicecatalog_factory import constants


def get(name, version):
    if name == "CDK" and version == "1.0.0":
        return CDK100Template()
    else:
        raise Exception(f"Unknown template {name}.{version} ")


def get_v2(name, pipeline_mode):
    if pipeline_mode == constants.PIPELINE_MODE_SPILT:
        if name == "stack":
            return builders_cfn.StackTemplateBuilder()
        elif name == "products":
            return builders_cfn.ProductTemplateBuilder()
        elif name == "workspace":
            return builders_noncfn.TerraformTemplateBuilder()
        elif name == "app":
            return builders_noncfn.CDKAppTemplateBuilder()
        else:
            raise Exception(f"Unsupported: {name} for {pipeline_mode}")
    elif pipeline_mode == constants.PIPELINE_MODE_COMBINED:
        if name == "stack":
            return builders_cfn_combined.StackTemplateBuilder()
        elif name == "products":
            return builders_cfn_combined.ProductTemplateBuilder()
        # elif name == "workspace":
        #     return builders_noncfn.TerraformTemplateBuilder()
        # elif name == "app":
        #     return builders_noncfn.CDKAppTemplateBuilder()
        else:
            raise Exception(f"Unsupported: {name} for {pipeline_mode}")
    else:
        raise Exception(f"Unsupported: {pipeline_mode}")
