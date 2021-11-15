#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
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
CFNNAG_PROJECT_NAME = "ServiceCatalog-Factory-SharedCFNNag"
RSPEC_PROJECT_NAME = "ServiceCatalog-Factory-SharedRSpec"
JINJA_PROJECT_NAME = "ServiceCatalog-Factory-SharedJINJA"
DEPLOY_IN_GOVCLOUD_PROJECT_NAME = "ServiceCatalog-Factory-SharedDeployInGovCloud"


def get_commands_for_deploy() -> list:
    commands = [
        "cd $SOURCE_PATH",
    ]
    for region in config.get_regions():
        commands.append(
            f"servicecatalog-factory create-or-update-provisioning-artifact-from-codepipeline-id $PIPELINE_NAME $AWS_REGION $CODEPIPELINE_ID {region}"
        )

    return commands


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
                EnvironmentVariables=[
                    codebuild.EnvironmentVariable(
                        Name="TEMPLATE_FORMAT", Type="PLAINTEXT", Value="yaml",
                    ),
                    codebuild.EnvironmentVariable(
                        Name="CATEGORY", Type="PLAINTEXT", Value="product",
                    ),
                    dict(Name="SOURCE_PATH", Value=".", Type="PLAINTEXT",),
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
                                        "cd $SOURCE_PATH",
                                        "export FactoryTemplateValidateBucket=$(aws cloudformation list-stack-resources --stack-name servicecatalog-factory --query 'StackResourceSummaries[?LogicalResourceId==`FactoryTemplateValidateBucket`].PhysicalResourceId' --output text)",
                                        "aws s3 cp $CATEGORY.template.$TEMPLATE_FORMAT s3://$FactoryTemplateValidateBucket/$CODEBUILD_BUILD_ID.$TEMPLATE_FORMAT",
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
                        Type="PLAINTEXT", Name="REGION", Value=t.Sub("${AWS::Region}"),
                    ),
                    codebuild.EnvironmentVariable(
                        Name="PIPELINE_NAME", Type="PLAINTEXT", Value="CHANGE_ME"
                    ),
                    codebuild.EnvironmentVariable(
                        Name="CODEPIPELINE_ID", Type="PLAINTEXT", Value="CHANGE_ME"
                    ),
                    codebuild.EnvironmentVariable(
                        Name="SOURCE_PATH", Type="PLAINTEXT", Value=".",
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
        codebuild.Project(
            "CFNNag",
            Name=CFNNAG_PROJECT_NAME,
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
                    ),
                    codebuild.EnvironmentVariable(
                        Name="CATEGORY", Type="PLAINTEXT", Value="stack",
                    ),
                    codebuild.EnvironmentVariable(
                        Name="SOURCE_PATH", Type="PLAINTEXT", Value=".",
                    ),
                ],
            ),
            Source=codebuild.Source(
                BuildSpec=t.Sub(
                    yaml.safe_dump(
                        dict(
                            version=0.2,
                            phases={
                                "install": {
                                    "runtime-versions": {"ruby": "2.x",},
                                    "commands": [
                                        "gem install cfn-nag",
                                        "cfn_nag_rules",
                                    ],
                                },
                                "build": {
                                    "commands": [
                                        "cd $SOURCE_PATH",
                                        "cfn_nag_scan --input-path ./$CATEGORY.template.$TEMPLATE_FORMAT",
                                    ]
                                },
                            },
                            artifacts=dict(files=["*", "**/*"],),
                        )
                    )
                ),
                Type="CODEPIPELINE",
            ),
            Description=t.Sub("Run cfn nag"),
        ),
        codebuild.Project(
            "RSpec",
            Name=RSPEC_PROJECT_NAME,
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
                    ),
                    codebuild.EnvironmentVariable(
                        Name="CATEGORY", Type="PLAINTEXT", Value="stack",
                    ),
                    codebuild.EnvironmentVariable(
                        Name="SOURCE_PATH", Type="PLAINTEXT", Value=".",
                    ),
                ],
            ),
            Source=codebuild.Source(
                BuildSpec=t.Sub(
                    yaml.safe_dump(
                        dict(
                            version=0.2,
                            phases={
                                "install": {
                                    "runtime-versions": {
                                        "ruby": "2.7",
                                        "python": "3.7",
                                    },
                                    "commands": [
                                        "gem install cloudformation_rspec",
                                        "gem install rspec_junit_formatter",
                                        "pip install cfn-lint",
                                    ],
                                },
                                "build": {
                                    "commands": [
                                        "cd $SOURCE_PATH",
                                        "rspec  --format progress --format RspecJunitFormatter --out reports/rspec.xml specs/",
                                    ]
                                },
                            },
                            reports=dict(
                                junit={
                                    "files": ["*", "**/*"],
                                    "base-directory": "reports",
                                    "file-format": "JUNITXML",
                                },
                            ),
                            artifacts=dict(files=["*", "**/*"],),
                        )
                    )
                ),
                Type="CODEPIPELINE",
            ),
            Description=t.Sub("Run cfn nag"),
        ),
        codebuild.Project(
            "Jinja",
            Name=JINJA_PROJECT_NAME,
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
                    ),
                    codebuild.EnvironmentVariable(
                        Name="CATEGORY", Type="PLAINTEXT", Value="stack",
                    ),
                    codebuild.EnvironmentVariable(
                        Name="SOURCE_PATH", Type="PLAINTEXT", Value=".",
                    ),
                ],
            ),
            Source=codebuild.Source(
                BuildSpec=t.Sub(
                    yaml.safe_dump(
                        dict(
                            version=0.2,
                            phases={
                                "install": {
                                    "runtime-versions": {"python": "3.7",},
                                    "commands": ["pip install Jinja2==2.10.1",],
                                },
                                "build": {
                                    "commands": [
                                        "cd $SOURCE_PATH",
                                        """
                                        python -c "from jinja2 import Template;print(Template(open('$CATEGORY.template.$TEMPLATE_FORMAT', 'r').read()).render())" > product.template.$TEMPLATE_FORMAT
                                        """,
                                    ]
                                },
                            },
                            reports=dict(
                                junit={
                                    "files": ["*", "**/*"],
                                    "base-directory": "reports",
                                    "file-format": "JUNITXML",
                                },
                            ),
                            artifacts=dict(files=["*", "**/*"],),
                        )
                    )
                ),
                Type="CODEPIPELINE",
            ),
            Description=t.Sub("Run cfn nag"),
        ),
    ]
