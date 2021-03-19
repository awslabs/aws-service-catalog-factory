# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import troposphere as t
from troposphere import codebuild
import yaml
from servicecatalog_factory import constants
from servicecatalog_factory.template_builder.base_template import (
    VALIDATE_OUTPUT_ARTIFACT,
)

VALIDATE_PROJECT_NAME = "ServiceCatalog-Factory-SharedValidate"


def get_resources() -> list:
    return [
        codebuild.Project(
            "Validate",
            Name=VALIDATE_PROJECT_NAME,
            ServiceRole=t.Sub(
                "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/DeliveryCodeRole"
            ),
            Tags=t.Tags.from_dict(**{"ServiceCatalogPuppet:Actor": "Framework"}),
            Artifacts=codebuild.Artifacts(Type="CODEPIPELINE"),
            TimeoutInMinutes=60,
            Environment=codebuild.Environment(
                ComputeType=constants.ENVIRONMENT_COMPUTE_TYPE_DEFAULT,
                Image=constants.ENVIRONMENT_IMAGE_DEFAULT,
                Type=constants.ENVIRONMENT_TYPE_DEFAULT,
            ),
            Source=codebuild.Source(
                BuildSpec=t.Sub(
                    yaml.safe_dump(
                        dict(
                            version=0.2,
                            phases=dict(
                                build={
                                    "commands": [
                                        "export FactoryTemplateValidateBucket=$(aws cloudformation list-stack-resources --stack-name servicecatalog-factory --query 'StackResourceSummaries[?LogicalResourceId==`FactoryTemplateValidateBucket`].PhysicalResourceId' --output text)",
                                        "aws s3 cp product.template.yaml s3://$FactoryTemplateValidateBucket/$CODEBUILD_BUILD_ID.yaml",
                                        "aws cloudformation validate-template --template-url https://$FactoryTemplateValidateBucket.s3.$AWS_REGION.amazonaws.com/$CODEBUILD_BUILD_ID.yaml",
                                    ]
                                },
                            ),
                            artifacts=dict(
                                name=VALIDATE_OUTPUT_ARTIFACT, files=["*", "**/*"],
                            ),
                        )
                    )
                ),
                Type="CODEPIPELINE",
            ),
            Description=t.Sub("Run validate"),
        ),
    ]
