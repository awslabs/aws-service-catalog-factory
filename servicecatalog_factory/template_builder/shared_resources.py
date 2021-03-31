# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import troposphere as t
from troposphere import codebuild
import yaml
from servicecatalog_factory import constants
from servicecatalog_factory import config
from servicecatalog_factory.template_builder.base_template import (
    VALIDATE_OUTPUT_ARTIFACT,
    DEPLOY_OUTPUT_ARTIFACT,
)

VALIDATE_PROJECT_NAME = "ServiceCatalog-Factory-SharedValidate"
DEPLOY_IN_GOVCLOUD_PROJECT_NAME = "ServiceCatalog-Factory-SharedDeployInGovCloud"


def get_commands_for_deploy() -> list:
    commands = []
    for region in config.get_regions():
        commands.append(
            f"servicecatalog-factory create-or-update-provisioning-artifact-from-codepipeline-id $PIPELINE_NAME $AWS_REGION $CODEPIPELINE_ID {region}"
        )

    return commands


def get_resources() -> list:
    all_regions = config.get_regions()

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
                EnvironmentVariables=[
                    codebuild.EnvironmentVariable(
                        Name="TEMPLATE_FORMAT", Type="PLAINTEXT", Value="yaml",
                    )
                ],
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
                                        "aws s3 cp product.template.$TEMPLATE_FORMAT s3://$FactoryTemplateValidateBucket/$CODEBUILD_BUILD_ID.$TEMPLATE_FORMAT",
                                        "aws cloudformation validate-template --template-url https://$FactoryTemplateValidateBucket.s3.$AWS_REGION.amazonaws.com/$CODEBUILD_BUILD_ID.$TEMPLATE_FORMAT",
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
        codebuild.Project(
            "Deploy",
            Name=DEPLOY_IN_GOVCLOUD_PROJECT_NAME,
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
                EnvironmentVariables=[
                    codebuild.EnvironmentVariable(
                        Type="PLAINTEXT",
                        Name="ACCOUNT_ID",
                        Value=t.Sub("${AWS::AccountId}"),
                    ),
                    codebuild.EnvironmentVariable(
                        Name="PIPELINE_NAME", Type="PLAINTEXT", Value="CHANGE_ME"
                    ),
                    codebuild.EnvironmentVariable(
                        Name="CODEPIPELINE_ID", Type="PLAINTEXT", Value="CHANGE_ME"
                    ),
                ],
            ),
            Source=codebuild.Source(
                BuildSpec=t.Sub(
                    yaml.safe_dump(
                        dict(
                            version=0.2,
                            phases=dict(
                                install={
                                    "runtime-versions": dict(
                                        python="3.7",
                                        nodejs=constants.BUILDSPEC_RUNTIME_VERSIONS_NODEJS_DEFAULT,
                                    ),
                                    "commands": [
                                        f"pip install {constants.VERSION}"
                                        if "http" in constants.VERSION
                                        else f"pip install aws-service-catalog-factory=={constants.VERSION}",
                                    ],
                                },
                                build={"commands": get_commands_for_deploy()},
                            ),
                            artifacts={
                                "name": DEPLOY_OUTPUT_ARTIFACT,
                                "files": ["*", "**/*"],
                            },
                        )
                    )
                ),
                Type="CODEPIPELINE",
            ),
            Description=t.Sub("Create a deploy stage for template cloudformation"),
        ),
    ]
