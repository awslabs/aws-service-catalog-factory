#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import json

import troposphere as t
import yaml

from servicecatalog_factory import utils
from servicecatalog_factory import constants
from troposphere import codepipeline
from troposphere import codebuild
from servicecatalog_factory.template_builder import base_template
from servicecatalog_factory.template_builder import builders_base


class NonCFNTemplateBuilder(builders_base.BaseTemplateBuilder):
    def build_package_stage(
        self, pipeline_stages, tpl, stages, options, category, source
    ):
        package_input_artifact_name = base_template.SOURCE_OUTPUT_ARTIFACT
        package_project_name = t.Sub("${AWS::StackName}-PackageProject")
        tpl.add_resource(
            codebuild.Project(
                "PackageProject",
                Name=package_project_name,
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
                            Name="CATEGORY", Type="PLAINTEXT", Value=category,
                        ),
                        codebuild.EnvironmentVariable(
                            Name="SOURCE_PATH", Type="PLAINTEXT", Value=".",
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
                                        "cd $SOURCE_PATH",
                                        f"echo '{json.dumps(utils.unwrap(options))}' > options.json",
                                        f"zip -r $CATEGORY.zip .",
                                    ],
                                }
                            },
                            "artifacts": {"files": ["*.zip"],},
                        }
                    ),
                    Type="CODEPIPELINE",
                ),
                Description=t.Sub("build project"),
            )
        )
        pipeline_stages.append(
            codepipeline.Stages(
                Name="Package",
                Actions=[
                    codepipeline.Actions(
                        Name="Package",
                        RunOrder=1,
                        RoleArn=t.Sub(
                            "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/SourceRole"
                        ),
                        InputArtifacts=[
                            codepipeline.InputArtifacts(
                                Name=package_input_artifact_name
                            ),
                        ],
                        ActionTypeId=codepipeline.ActionTypeId(
                            Category="Build",
                            Owner="AWS",
                            Version="1",
                            Provider="CodeBuild",
                        ),
                        OutputArtifacts=[
                            codepipeline.OutputArtifacts(
                                Name=base_template.PACKAGE_OUTPUT_ARTIFACT
                            )
                        ],
                        Configuration={
                            "ProjectName": package_project_name,
                            "EnvironmentVariables": t.Sub(
                                json.dumps(
                                    [
                                        dict(
                                            name="SOURCE_PATH",
                                            value=source.get("Path", "."),
                                            type="PLAINTEXT",
                                        ),
                                    ]
                                )
                            ),
                        },
                    )
                ],
            )
        )

    def build_deploy_stage(self, pipeline_stages, tpl, name, version, category):
        deploy_project_name = t.Sub("${AWS::StackName}-DeployProject")
        tpl.add_resource(
            codebuild.Project(
                "DeployProject",
                Name=deploy_project_name,
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
                            Name="CATEGORY", Type="PLAINTEXT", Value=category,
                        ),
                        codebuild.EnvironmentVariable(
                            Name="ACCOUNT_ID",
                            Type="PLAINTEXT",
                            Value=t.Sub("${AWS::AccountId}"),
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
                                        f"aws s3 cp $CATEGORY.zip s3://sc-puppet-stacks-repository-$ACCOUNT_ID/$CATEGORY/{name}/{version}/$CATEGORY.zip"
                                    ],
                                }
                            },
                            "artifacts": {"files": ["*", "**/*"],},
                        }
                    ),
                    Type="CODEPIPELINE",
                ),
                Description=t.Sub("deploy project"),
            )
        )

        pipeline_stages.append(
            codepipeline.Stages(
                Name="Deploy",
                Actions=[
                    codepipeline.Actions(
                        Name="Deploy",
                        RunOrder=1,
                        RoleArn=t.Sub(
                            "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/SourceRole"
                        ),
                        InputArtifacts=[
                            codepipeline.InputArtifacts(
                                Name=base_template.PACKAGE_OUTPUT_ARTIFACT
                            ),
                        ],
                        ActionTypeId=codepipeline.ActionTypeId(
                            Category="Build",
                            Owner="AWS",
                            Version="1",
                            Provider="CodeBuild",
                        ),
                        OutputArtifacts=[
                            codepipeline.OutputArtifacts(
                                Name=base_template.DEPLOY_OUTPUT_ARTIFACT
                            )
                        ],
                        Configuration={"ProjectName": deploy_project_name,},
                    )
                ],
            )
        )


class TerraformTemplateBuilder(NonCFNTemplateBuilder):
    def build(self, name, version, source, options, stages):
        factory_version = constants.VERSION
        template_description = f'{{"version": "{factory_version}", "framework": "servicecatalog-factory", "role": "product-pipeline", "type": "cloudformation", "category": "workspace"}}'
        tpl = t.Template(Description=template_description)

        pipeline_stages = []

        self.build_source_stage(tpl, pipeline_stages, source)
        if stages.get("Tests"):
            actions = []
            self.add_custom_tests(
                tpl, stages, actions, base_template.SOURCE_OUTPUT_ARTIFACT
            )
            pipeline_stages.append(codepipeline.Stages(Name="Tests", Actions=actions))
        self.build_package_stage(
            pipeline_stages, tpl, stages, options, "workspace", source
        )
        self.build_deploy_stage(pipeline_stages, tpl, name, version, "workspace")
        tpl.add_resource(
            codepipeline.Pipeline(
                "Pipeline",
                RoleArn=t.Sub(
                    "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/CodePipelineRole"
                ),
                Stages=pipeline_stages,
                Name=t.Sub("${AWS::StackName}-pipeline"),
                ArtifactStore=codepipeline.ArtifactStore(
                    Type="S3",
                    Location=t.Sub(
                        "sc-factory-artifacts-${AWS::AccountId}-${AWS::Region}"
                    ),
                ),
                RestartExecutionOnUpdate=False,
            ),
        )

        return tpl


class CDKAppTemplateBuilder(NonCFNTemplateBuilder):
    def build(self, name, version, source, options, stages):
        factory_version = constants.VERSION
        template_description = f'{{"version": "{factory_version}", "framework": "servicecatalog-factory", "role": "product-pipeline", "type": "cloudformation", "category": "app"}}'
        tpl = t.Template(Description=template_description)

        pipeline_stages = []

        self.build_source_stage(tpl, pipeline_stages, source)
        if stages.get("Tests"):
            actions = []
            self.add_custom_tests(
                tpl, stages, actions, base_template.SOURCE_OUTPUT_ARTIFACT
            )
            pipeline_stages.append(codepipeline.Stages(Name="Tests", Actions=actions))
        self.build_package_stage(pipeline_stages, tpl, stages, options, "app", source)
        self.build_deploy_stage(pipeline_stages, tpl, name, version, "app")

        tpl.add_resource(
            codepipeline.Pipeline(
                "Pipeline",
                RoleArn=t.Sub(
                    "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/CodePipelineRole"
                ),
                Stages=pipeline_stages,
                Name=t.Sub("${AWS::StackName}-pipeline"),
                ArtifactStore=codepipeline.ArtifactStore(
                    Type="S3",
                    Location=t.Sub(
                        "sc-factory-artifacts-${AWS::AccountId}-${AWS::Region}"
                    ),
                ),
                RestartExecutionOnUpdate=False,
            ),
        )

        return tpl
