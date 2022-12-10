#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import json

import troposphere as t
import yaml
from troposphere import codepipeline, codebuild

from servicecatalog_factory import config
from servicecatalog_factory import constants
from servicecatalog_factory.template_builder import base_template, shared_resources
from servicecatalog_factory.template_builder.pipeline.utils import (
    translate_category,
    is_for_single_version,
)
from servicecatalog_factory.template_builder.troposphere_contstants import (
    codebuild as codebuild_troposphere_constants,
)


class DeployTemplateMixin:
    def generate_deploy_stage(self, tpl, item, versions, stages, input_artifact_name):
        if self.category in ["products", "product"]:
            return self.generate_deploy_stage_for_products(
                tpl, item, versions, stages, input_artifact_name
            )
        else:
            return self.generate_deploy_stage_for_non_products(
                tpl, item, versions, stages, input_artifact_name
            )

    def generate_deploy_stage_for_products(
        self, tpl, item, versions, stages, input_artifact_name
    ):
        all_regions = config.get_regions()

        input_artifacts = list()
        output_artifacts = list()
        common_commands = list()
        secondary_artifacts = dict()
        count = 0
        common_commands.append("env")
        for version in versions:
            version_name = version.get("Name")
            base_directory = (
                "$CODEBUILD_SRC_DIR"
                if count == 0
                else f"$CODEBUILD_SRC_DIR_Package_{version_name}"
            )
            input_artifacts.append(
                codepipeline.InputArtifacts(
                    Name=f"{input_artifact_name}_{version_name}"
                ),
            )
            output_artifacts.append(
                codepipeline.OutputArtifacts(
                    Name=f"{base_template.DEPLOY_OUTPUT_ARTIFACT}_{version_name}"
                ),
            )
            secondary_artifacts[f"Deploy_{version_name}"] = {
                "base-directory": base_directory,
                "files": "**/*",
            }
            count += 1

        common_commands.extend(
            ['eval "cd \$$TRIGGERING_PACKAGE"', "pwd", "cd ${SOURCE_PATH}", "pwd",]
        )

        common_commands.extend(
            [
                f"servicecatalog-factory create-or-update-provisioning-artifact-from-codepipeline-id $PIPELINE_NAME $AWS_REGION $PIPELINE_EXECUTION_ID {region}"
                for region in all_regions
            ]
        )
        build_spec = yaml.safe_dump(
            {
                "version": "0.2",
                "phases": {
                    "install": {
                        "runtime-versions": {"python": "3.7"},
                        "commands": [
                            f"pip install {constants.VERSION}"
                            if "http" in constants.VERSION
                            else f"pip install aws-service-catalog-factory=={constants.VERSION}",
                        ],
                    },
                    "build": {"commands": common_commands,},
                },
                "artifacts": {
                    "files": ["*", "**/*"],
                    "secondary-artifacts": secondary_artifacts,
                },
            }
        )

        tpl.add_resource(
            codebuild.Project(
                "DeployProject",
                Name=t.Sub("${AWS::StackName}-DeployProject"),
                ServiceRole=t.Sub(
                    "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/DeliveryCodeRole"
                ),
                Tags=t.Tags.from_dict(**{"ServiceCatalogPuppet:Actor": "Framework"}),
                Artifacts=codebuild.Artifacts(Type="CODEPIPELINE"),
                TimeoutInMinutes=60,
                Environment=codebuild.Environment(
                    ComputeType=constants.ENVIRONMENT_COMPUTE_TYPE_DEFAULT,
                    Image=stages.get("Build", {}).get(
                        "BuildSpecImage", constants.ENVIRONMENT_IMAGE_DEFAULT
                    ),
                    Type=constants.ENVIRONMENT_TYPE_DEFAULT,
                    EnvironmentVariables=[
                        codebuild.EnvironmentVariable(
                            Type="PLAINTEXT",
                            Name="ACCOUNT_ID",
                            Value=t.Sub("${AWS::AccountId}"),
                        ),
                        codebuild.EnvironmentVariable(
                            Type="PLAINTEXT",
                            Name="REGION",
                            Value=t.Sub("${AWS::Region}"),
                        ),
                        codebuild.EnvironmentVariable(
                            Name="PIPELINE_NAME", Type="PLAINTEXT", Value="CHANGE_ME"
                        ),
                        codebuild.EnvironmentVariable(
                            Name="PIPELINE_EXECUTION_ID",
                            Type="PLAINTEXT",
                            Value="CHANGE_ME",
                        ),
                        codebuild.EnvironmentVariable(
                            Name="SOURCE_PATH", Type="PLAINTEXT", Value=".",
                        ),
                        codebuild.EnvironmentVariable(
                            Name="AWS_URL_SUFFIX",
                            Type="PLAINTEXT",
                            Value=t.Ref("AWS::URLSuffix"),
                        ),
                    ],
                ),
                Source=codebuild.Source(BuildSpec=build_spec, Type="CODEPIPELINE",),
                Description=t.Sub("build project"),
            )
        )

        return codepipeline.Stages(
            Name="Deploy",
            Actions=[
                codepipeline.Actions(
                    Name="Deploy",
                    RunOrder=1,
                    RoleArn=t.Sub(
                        "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/SourceRole"
                    ),
                    InputArtifacts=input_artifacts,
                    ActionTypeId=codebuild_troposphere_constants.ACTION_TYPE_ID_FOR_BUILD,
                    OutputArtifacts=output_artifacts,
                    Configuration={
                        "ProjectName": t.Ref("DeployProject"),
                        "PrimarySource": f"{input_artifact_name}_{versions[0].get('Name')}",
                        "EnvironmentVariables": t.Sub(
                            json.dumps(
                                [
                                    dict(
                                        name="CATEGORY",
                                        type="PLAINTEXT",
                                        value=translate_category(self.category),
                                    ),
                                    dict(
                                        name="TEMPLATE_FORMAT",
                                        type="PLAINTEXT",
                                        value="yaml",
                                    ),
                                    dict(
                                        name="PROVISIONER",
                                        value="cloudformation",
                                        type="PLAINTEXT",
                                    ),
                                    dict(
                                        name="PIPELINE_NAME",
                                        value="${AWS::StackName}-pipeline",
                                        type="PLAINTEXT",
                                    ),
                                    dict(
                                        name="PIPELINE_EXECUTION_ID",
                                        value="#{codepipeline.PipelineExecutionId}",
                                        type="PLAINTEXT",
                                    ),
                                    dict(
                                        name="TRIGGERING_SOURCE",
                                        type="PLAINTEXT",
                                        value="#{BuildVariables.TRIGGERING_SOURCE}",
                                    ),
                                    dict(
                                        name="TRIGGERING_PACKAGE",
                                        type="PLAINTEXT",
                                        value="#{BuildVariables.TRIGGERING_PACKAGE}",
                                    ),
                                    dict(
                                        name="SOURCE_PATH",
                                        type="PLAINTEXT",
                                        value="#{BuildVariables.SOURCE_PATH}",
                                    ),
                                    dict(
                                        name="NAME",
                                        type="PLAINTEXT",
                                        value="#{BuildVariables.NAME}",
                                    ),
                                    dict(
                                        name="VERSION",
                                        type="PLAINTEXT",
                                        value="#{BuildVariables.VERSION}",
                                    ),
                                ]
                            )
                        ),
                    },
                )
            ],
        )

    def generate_deploy_stage_for_non_products(
        self, tpl, item, versions, stages, input_artifact_name
    ):

        environment_variables = [
            dict(name="CATEGORY", type="PLAINTEXT", value=self.category,),
            dict(
                name="TRIGGERING_SOURCE",
                type="PLAINTEXT",
                value="#{BuildVariables.TRIGGERING_SOURCE}",
            ),
            dict(
                name="TRIGGERING_PACKAGE",
                type="PLAINTEXT",
                value="#{BuildVariables.TRIGGERING_PACKAGE}",
            ),
            dict(
                name="SOURCE_PATH",
                type="PLAINTEXT",
                value="#{BuildVariables.SOURCE_PATH}",
            ),
            dict(name="NAME", type="PLAINTEXT", value="#{BuildVariables.NAME}",),
            dict(name="VERSION", type="PLAINTEXT", value="#{BuildVariables.VERSION}",),
        ]

        input_artifacts = list()
        output_artifacts = list()
        secondary_artifacts = dict()

        count = 0
        for version in versions:
            version_name = version.get("Name")
            base_directory = (
                "$CODEBUILD_SRC_DIR"
                if count == 0
                else f"$CODEBUILD_SRC_DIR_Package_{version_name}"
            )
            input_artifacts.append(
                codepipeline.InputArtifacts(
                    Name=f"{input_artifact_name}_{version_name}"
                ),
            )
            output_artifacts.append(
                codepipeline.OutputArtifacts(
                    Name=f"{base_template.DEPLOY_OUTPUT_ARTIFACT}_{version_name}"
                ),
            )
            secondary_artifacts[f"Deploy_{version_name}"] = {
                "base-directory": base_directory,
                "files": "**/*",
            }
            count += 1

        if is_for_single_version(versions):
            project_name = shared_resources.SINGLE_PROJECTS_BY_CATEGORY[self.category]
            version = versions[0]
            if self.category == "stack":
                environment_variables.append(
                    dict(
                        name="TEMPLATE_FORMAT",
                        type="PLAINTEXT",
                        value=version.get("Provisioner", {}).get(
                            "Format", item.get("Provisioner", {}).get("Format", "yaml")
                        ),
                    ),
                )

        else:
            project_name = t.Ref("DeployProject")
            tpl.add_resource(
                codebuild.Project(
                    "DeployProject",
                    Name=t.Sub("${AWS::StackName}-DeployProject"),
                    ServiceRole=t.Sub(
                        "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/DeliveryCodeRole"
                    ),
                    Tags=t.Tags.from_dict(
                        **{"ServiceCatalogPuppet:Actor": "Framework"}
                    ),
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
                                Name="SOURCE_PATH", Type="PLAINTEXT", Value="NOT_SET",
                            ),
                            codebuild.EnvironmentVariable(
                                Name="TRIGGERING_SOURCE",
                                Type="PLAINTEXT",
                                Value="NOT_SET",
                            ),
                            codebuild.EnvironmentVariable(
                                Name="TRIGGERING_PACKAGE",
                                Type="PLAINTEXT",
                                Value="NOT_SET",
                            ),
                            codebuild.EnvironmentVariable(
                                Name="CATEGORY", Type="PLAINTEXT", Value="NOT_SET",
                            ),
                            codebuild.EnvironmentVariable(
                                Name="NAME", Type="PLAINTEXT", Value="NOT_SET",
                            ),
                            codebuild.EnvironmentVariable(
                                Name="VERSION", Type="PLAINTEXT", Value="NOT_SET",
                            ),
                        ],
                    ),
                    Source=codebuild.Source(
                        BuildSpec=yaml.safe_dump(
                            {
                                "version": "0.2",
                                "phases": {
                                    "build": {
                                        "commands": [
                                            "env",
                                            "pwd",
                                            'eval "cd \$$TRIGGERING_PACKAGE"',
                                            "pwd",
                                            "cd ${SOURCE_PATH}",
                                            "pwd",
                                            "aws s3 cp $CATEGORY.zip s3://sc-puppet-stacks-repository-$ACCOUNT_ID/$CATEGORY/$NAME/$VERSION/$CATEGORY.zip",
                                        ]
                                    },
                                },
                                "artifacts": {
                                    "files": ["*", "**/*"],
                                    "secondary-artifacts": secondary_artifacts,
                                },
                            }
                        ),
                        Type="CODEPIPELINE",
                    ),
                    Description=t.Sub("build project"),
                )
            )
            if self.category == "stack":
                environment_variables.append(
                    dict(
                        name="TEMPLATE_FORMAT",
                        type="PLAINTEXT",
                        value=item.get("Provisioner", {}).get("Format", "yaml"),
                    ),
                )

        return codepipeline.Stages(
            Name="Deploy",
            Actions=[
                codepipeline.Actions(
                    Name="Deploy",
                    RunOrder=1,
                    RoleArn=t.Sub(
                        "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/SourceRole"
                    ),
                    InputArtifacts=input_artifacts,
                    ActionTypeId=codebuild_troposphere_constants.ACTION_TYPE_ID_FOR_DEPLOY,
                    OutputArtifacts=output_artifacts,
                    Configuration={
                        "ProjectName": project_name,
                        "PrimarySource": input_artifacts[0].Name,
                        "EnvironmentVariables": t.Sub(
                            json.dumps(environment_variables)
                        ),
                    },
                )
            ],
        )
