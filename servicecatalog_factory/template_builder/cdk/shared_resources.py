#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import troposphere as t
from troposphere import codebuild
import yaml
from servicecatalog_factory import constants
from servicecatalog_factory import config
from servicecatalog_factory.template_builder.base_template import (
    PACKAGE_OUTPUT_ARTIFACT,
    DEPLOY_OUTPUT_ARTIFACT,
)

CDK_PACKAGE_PROJECT_NAME = "CDK-Package--1-0-0"
CDK_DEPLOY_PROJECT_NAME = "CDK-Deploy--1-0-0"


def get_commands_for_deploy() -> list:
    commands = []
    for region in config.get_regions():
        commands.append(
            f"servicecatalog-factory create-or-update-provisioning-artifact-from-codepipeline-id $PIPELINE_NAME $AWS_REGION $PIPELINE_EXECUTION_ID {region}"
        )
    return commands


def get_resources() -> list:
    all_regions = config.get_regions()
    return [
        codebuild.Project(
            "CDKPackage100",
            Name=CDK_PACKAGE_PROJECT_NAME,
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
                    {
                        "Type": "PLAINTEXT",
                        "Name": "ACCOUNT_ID",
                        "Value": t.Sub("${AWS::AccountId}"),
                    },
                    {"Type": "PLAINTEXT", "Name": "NAME", "Value": "CHANGE_ME"},
                    {"Type": "PLAINTEXT", "Name": "VERSION", "Value": "CHANGE_ME"},
                    {
                        "Type": "PLAINTEXT",
                        "Name": "PIPELINE_EXECUTION_ID",
                        "Value": "CHANGE_ME",
                    },
                    {
                        "Type": "PLAINTEXT",
                        "Name": "PIPELINE_NAME",
                        "Value": "CHANGE_ME",
                    },
                    {
                        "Type": "PLAINTEXT",
                        "Name": "TEMPLATE_FORMAT",
                        "Value": "CHANGE_ME",
                    },
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
                                        'zip -r $NAME-$VERSION.zip . -x "node_modules/*"'
                                    ]
                                    + [
                                        f"aws cloudformation package --region {region} --template $(pwd)/product.template.yaml --s3-bucket sc-factory-artifacts-$ACCOUNT_ID-{region} --s3-prefix /CDK/1.0.0/$NAME/$VERSION --output-template-file product.template-{region}.yaml"
                                        for region in all_regions
                                    ]
                                    + [
                                        f"aws s3 cp --quiet $NAME-$VERSION.zip s3://sc-factory-artifacts-$ACCOUNT_ID-{region}/CDK/1.0.0/$NAME/$VERSION/$NAME-$VERSION.zip"
                                        for region in all_regions
                                    ]
                                },
                            ),
                            artifacts={
                                "name": PACKAGE_OUTPUT_ARTIFACT,
                                "files": ["product.template-*.yaml"],
                            },
                        )
                    )
                ),
                Type="CODEPIPELINE",
            ),
            Description=t.Sub("Create a build stage for template CDK 1.0.0"),
        ),
        codebuild.Project(
            "CDKDeploy100",
            Name=CDK_DEPLOY_PROJECT_NAME,
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
                        Name="PIPELINE_EXECUTION_ID",
                        Type="PLAINTEXT",
                        Value="CHANGE_ME",
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
                                    "runtime-versions": dict(python="3.7",),
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
            Description=t.Sub("Create a deploy stage for template CDK 1.0.0"),
        ),
    ]
