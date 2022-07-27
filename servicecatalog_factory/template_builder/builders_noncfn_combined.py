#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import json

import troposphere as t
import yaml
import jinja2
from deepmerge import always_merger

from servicecatalog_factory import config
from servicecatalog_factory import constants
from troposphere import codepipeline
from troposphere import codebuild
from servicecatalog_factory.template_builder import base_template
from servicecatalog_factory.template_builder import shared_resources
from servicecatalog_factory.template_builder import builders_base
from servicecatalog_factory.template_builder.troposphere_contstants import (
    codebuild as codebuild_troposphere_constants,
)
from servicecatalog_factory.template_builder import builders_cfn_combined
from servicecatalog_factory import utils


class NonCFNCombinedTemplateBuilder(builders_cfn_combined.CFNCombinedTemplateBuilder):
    category = "notset"

    def build(self, name, item, versions, options, stages):
        factory_version = constants.VERSION
        template_description = f'{{"version": "{factory_version}", "framework": "servicecatalog-factory", "role": "product-pipeline", "type": "cloudformation", "category": "{self.category}"}}'
        tpl = t.Template(Description=template_description)

        build_input_artifact_name = base_template.SOURCE_OUTPUT_ARTIFACT
        test_input_artifact_name = build_input_artifact_name
        package_input_artifact_name = build_input_artifact_name
        deploy_input_artifact_name = base_template.PACKAGE_OUTPUT_ARTIFACT

        if stages.get("Build", {}).get("BuildSpec"):
            test_input_artifact_name = base_template.BUILD_OUTPUT_ARTIFACT
            package_input_artifact_name = base_template.BUILD_OUTPUT_ARTIFACT

        pipeline_stages = [
            self.build_source_stage(tpl, item, versions),
        ]
        if stages.get("Build"):
            pipeline_stages.append(
                self.build_build_stage(tpl, item, versions, build_input_artifact_name),
            )
        if stages.get("Tests"):
            pipeline_stages.append(
                self.build_test_stage(tpl, item, versions, test_input_artifact_name),
            )

        pipeline_stages.extend(
            [
                self.build_package_stage(
                    tpl, item, versions, package_input_artifact_name, options
                ),
                self.build_deploy_stage(
                    tpl, item, versions, deploy_input_artifact_name
                ),
            ]
        )
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

    def build_test_stage(self, tpl, item, versions, test_input_artifact_name):
        input_artifacts = list()
        for version in versions:
            version_name = version.get("Name")
            input_artifacts.append(
                codepipeline.InputArtifacts(
                    Name=f"{test_input_artifact_name}_{version_name}"
                ),
            )

        common_args = dict(
            RunOrder=1,
            InputArtifacts=input_artifacts,
            RoleArn=t.Sub(
                "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/SourceRole"
            ),
            ActionTypeId=codebuild_troposphere_constants.ACTION_TYPE_ID_FOR_TEST,
        )

        actions = list()

        custom_test_stages = item.get("Stages", {}).get("Tests", {})
        for test_stage_name, test_stage_details in custom_test_stages.items():
            test_output_artifacts = list()
            for version in versions:
                version_name = version.get("Name")
                test_output_artifacts.append(
                    codepipeline.OutputArtifacts(
                        Name=f"{test_stage_name}_{version_name}"
                    ),
                )
            common_args["OutputArtifacts"] = test_output_artifacts
            actions.extend(
                self.build_test_stage_action_for(
                    test_stage_name,
                    yaml.safe_load(test_stage_details.get("BuildSpec")),
                    common_args,
                    test_input_artifact_name,
                    tpl,
                    versions,
                )
            )

        return codepipeline.Stages(Name="Tests", Actions=actions)

    def build_package_stage(self, tpl, item, versions, input_artifact_name, options):
        all_regions = config.get_regions()
        stages = item.get("Stages", {})
        package_stage = stages.get("Package", {})

        if package_stage.get("BuildSpec"):
            package_build_spec = package_stage.get("BuildSpec")
            package_build_spec = jinja2.Template(package_build_spec).render(
                ALL_REGIONS=all_regions
            )
        else:
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
                    else f"$CODEBUILD_SRC_DIR_Validate_{version_name}"
                )
                input_artifacts.append(
                    codepipeline.InputArtifacts(
                        Name=f"{input_artifact_name}_{version_name}"
                    ),
                )
                output_artifacts.append(
                    codepipeline.OutputArtifacts(
                        Name=f"{base_template.PACKAGE_OUTPUT_ARTIFACT}_{version_name}"
                    ),
                )
                secondary_artifacts[f"Package_{version_name}"] = {
                    "base-directory": base_directory,
                    "files": "**/*",
                }
                count += 1

            common_commands.extend(
                [
                    "export TRIGGERING_SOURCE=$(servicecatalog-factory print-source-directory ${AWS::StackName}-pipeline $PIPELINE_EXECUTION_ID)",
                    "cd $TRIGGERING_SOURCE",
                    "pwd",
                    "export NAME=$(cat item_name.txt)",
                    "export VERSION=$(cat version_name.txt)",
                    "export SOURCE_PATH=$(cat path.txt)",
                    "cd $SOURCE_PATH",
                    "pwd",
                ]
            )
            package_build_spec = yaml.safe_dump(
                {
                    "version": "0.2",
                    "env": {
                        "variables": {
                            "TRIGGERING_SOURCE": "NOT_SET",
                            "NAME": "NOT_SET",
                            "VERSION": "NOT_SET",
                            "SOURCE_PATH": "NOT_SET",
                        },
                        "exported-variables": [
                            "TRIGGERING_SOURCE",
                            "NAME",
                            "VERSION",
                            "SOURCE_PATH",
                        ],
                    },
                    "phases": {
                        "install": {
                            "runtime-versions": dict(python="3.7",),
                            "commands": [
                                f"pip install {constants.VERSION}"
                                if "http" in constants.VERSION
                                else f"pip install aws-service-catalog-factory=={constants.VERSION}",
                            ],
                        },
                        "build": {
                            "commands": common_commands
                            + [
                                f"echo '{json.dumps(utils.unwrap(options))}' > options.json",
                                f"zip -r $CATEGORY.zip .",
                            ],
                        },
                    },
                    "artifacts": {
                        "files": ["*", "**/*"],
                        "secondary-artifacts": secondary_artifacts,
                    },
                }
            )

        tpl.add_resource(
            codebuild.Project(
                "PackageProject",
                Name=t.Sub("${AWS::StackName}-PackageProject"),
                ServiceRole=t.Sub(
                    "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/DeliveryCodeRole"
                ),
                Tags=t.Tags.from_dict(**{"ServiceCatalogPuppet:Actor": "Framework"}),
                Artifacts=codebuild.Artifacts(Type="CODEPIPELINE"),
                TimeoutInMinutes=60,
                Environment=codebuild.Environment(
                    ComputeType=constants.ENVIRONMENT_COMPUTE_TYPE_DEFAULT,
                    Image=package_stage.get(
                        "BuildSpecImage", constants.ENVIRONMENT_IMAGE_DEFAULT
                    ),
                    Type=constants.ENVIRONMENT_TYPE_DEFAULT,
                ),
                Source=codebuild.Source(
                    BuildSpec=package_build_spec, Type="CODEPIPELINE",
                ),
                Description=t.Sub("build project"),
            )
        )

        return codepipeline.Stages(
            Name="Package",
            Actions=[
                codepipeline.Actions(
                    Name="Package",
                    RunOrder=1,
                    RoleArn=t.Sub(
                        "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/SourceRole"
                    ),
                    InputArtifacts=input_artifacts,
                    ActionTypeId=codebuild_troposphere_constants.ACTION_TYPE_ID_FOR_BUILD,
                    Namespace="BuildVariables",
                    OutputArtifacts=output_artifacts,
                    Configuration={
                        "ProjectName": t.Ref("PackageProject"),
                        "PrimarySource": f"{input_artifact_name}_{versions[0].get('Name')}",
                        "EnvironmentVariables": t.Sub(
                            json.dumps(
                                [
                                    dict(
                                        name="TEMPLATE_FORMAT",
                                        type="PLAINTEXT",
                                        value="yaml",
                                    ),
                                    dict(
                                        name="CATEGORY",
                                        type="PLAINTEXT",
                                        value=self.category,
                                    ),
                                    dict(
                                        name="PROVISIONER",
                                        type="PLAINTEXT",
                                        value="cloudformation",
                                    ),
                                    dict(
                                        name="ACCOUNT_ID",
                                        type="PLAINTEXT",
                                        value="${AWS::AccountId}",
                                    ),
                                    dict(
                                        name="STACK_NAME",
                                        type="PLAINTEXT",
                                        value="${AWS::StackName}",
                                    ),
                                    dict(
                                        name="PIPELINE_NAME",
                                        type="PLAINTEXT",
                                        value="${AWS::StackName}-pipeline",
                                    ),
                                    dict(
                                        name="PIPELINE_EXECUTION_ID",
                                        type="PLAINTEXT",
                                        value="#{codepipeline.PipelineExecutionId}",
                                    ),
                                    dict(
                                        name="TRIGGERING_SOURCE",
                                        type="PLAINTEXT",
                                        value="#{BuildVariables.TRIGGERING_SOURCE}",
                                    ),
                                    dict(
                                        name="SOURCE_PATH",
                                        type="PLAINTEXT",
                                        value="#{BuildVariables.SOURCE_PATH}",
                                    ),
                                    dict(
                                        name="ALL_REGIONS",
                                        type="PLAINTEXT",
                                        value=" ".join(all_regions),
                                    ),
                                ]
                            )
                        ),
                    },
                )
            ],
        )

    def build_deploy_stage(self, tpl, item, versions, input_artifact_name):
        stages = item.get("Stages", {})

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
            ["cd ${TRIGGERING_SOURCE}", "pwd", "cd ${SOURCE_PATH}", "pwd",]
        )
        package_build_spec = yaml.safe_dump(
            {
                "version": "0.2",
                "phases": {
                    "build": {
                        "commands": common_commands
                        + [
                            "aws s3 cp $CATEGORY.zip s3://sc-puppet-stacks-repository-$ACCOUNT_ID/$CATEGORY/$NAME/$VERSION/$CATEGORY.zip"
                        ],
                    },
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
                    ],
                ),
                Source=codebuild.Source(
                    BuildSpec=package_build_spec, Type="CODEPIPELINE",
                ),
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
                                        value=self.category,
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


class CDKAppTemplateBuilder(NonCFNCombinedTemplateBuilder):
    category = "app"


class TerraformTemplateBuilder(NonCFNCombinedTemplateBuilder):
    category = "workspace"
