#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import json

import troposphere as t
from troposphere import codepipeline, codebuild

from servicecatalog_factory import constants
from servicecatalog_factory.template_builder import base_template
from servicecatalog_factory.template_builder.pipeline.utils import translate_category
from servicecatalog_factory.template_builder.troposphere_contstants import (
    codebuild as codebuild_troposphere_constants,
)


class BuildTemplateMixin:
    def has_a_build_stage(self, stages):
        return stages.get("Build")

    def generate_build_stage(
        self, tpl, versions, stages, input_artifact_name
    ) -> codepipeline.Stages:
        build_stage = stages.get("Build", {})
        version = versions[0]
        version_name = version.get("Name")
        path = version.get("Source", {}).get("Path", ".")
        input_artifact_name_to_use = f"{input_artifact_name}_{version_name}"

        tpl.add_resource(
            codebuild.Project(
                "BuildProject",
                Name=t.Sub("${AWS::StackName}-BuildProject"),
                ServiceRole=t.Sub(
                    "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/DeliveryCodeRole"
                ),
                Tags=t.Tags.from_dict(**{"ServiceCatalogPuppet:Actor": "Framework"}),
                Artifacts=codebuild.Artifacts(Type="CODEPIPELINE"),
                TimeoutInMinutes=build_stage.get(
                    "TimeoutInMinutes", constants.BUILD_STAGE_TIMEOUT_IN_MINUTES_DEFAULT
                ),
                Environment=codebuild.Environment(
                    ComputeType=build_stage.get(
                        "BuildEnvironmentComputeType",
                        constants.ENVIRONMENT_COMPUTE_TYPE_DEFAULT,
                    ),
                    Image=build_stage.get(
                        "BuildSpecImage", constants.ENVIRONMENT_IMAGE_DEFAULT
                    ),
                    Type=build_stage.get(
                        "EnvironmentType", constants.ENVIRONMENT_TYPE_DEFAULT
                    ),
                    PrivilegedMode=build_stage.get(
                        "PrivilegedMode",
                        constants.GENERIC_BUILD_PROJECT_PRIVILEGED_MODE_DEFAULT,
                    ),
                    EnvironmentVariables=[
                        codebuild.EnvironmentVariable(
                            Name="TEMPLATE_FORMAT", Type="PLAINTEXT", Value="yaml",
                        ),
                        codebuild.EnvironmentVariable(
                            Name="CATEGORY",
                            Type="PLAINTEXT",
                            Value=translate_category(self.category),
                        ),
                        codebuild.EnvironmentVariable(
                            Name="SOURCE_PATH", Type="PLAINTEXT", Value=".",
                        ),
                    ],
                ),
                Source=codebuild.Source(
                    BuildSpec=build_stage.get("BuildSpec"), Type="CODEPIPELINE",
                ),
                Description=t.Sub("build project"),
            )
        )

        return codepipeline.Stages(
            Name="Build",
            Actions=[
                codepipeline.Actions(
                    Name="Build",
                    RunOrder=1,
                    RoleArn=t.Sub(
                        "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/SourceRole"
                    ),
                    InputArtifacts=[
                        codepipeline.InputArtifacts(Name=input_artifact_name_to_use),
                    ],
                    ActionTypeId=codebuild_troposphere_constants.ACTION_TYPE_ID_FOR_BUILD,
                    OutputArtifacts=[
                        codepipeline.OutputArtifacts(
                            Name=f"{base_template.BUILD_OUTPUT_ARTIFACT}_{version_name}"
                        )
                    ],
                    Configuration={
                        "ProjectName": t.Sub("${AWS::StackName}-BuildProject"),
                        "PrimarySource": input_artifact_name_to_use,
                        "EnvironmentVariables": t.Sub(
                            json.dumps(
                                [
                                    dict(
                                        name="TEMPLATE_FORMAT",
                                        value="yaml",
                                        type="PLAINTEXT",
                                    ),
                                    dict(
                                        name="CATEGORY",
                                        value=translate_category(self.category),
                                        type="PLAINTEXT",
                                    ),
                                    dict(
                                        name="SOURCE_PATH",
                                        value=path,
                                        type="PLAINTEXT",
                                    ),
                                ]
                            )
                        ),
                    },
                )
            ],
        )
