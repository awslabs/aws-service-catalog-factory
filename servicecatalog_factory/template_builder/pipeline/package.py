#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import json

import jinja2
import troposphere as t
import yaml
from troposphere import codepipeline, codebuild

from servicecatalog_factory import config
from servicecatalog_factory import constants
from servicecatalog_factory import utils
from servicecatalog_factory.template_builder import base_template
from servicecatalog_factory.template_builder.pipeline.utils import (
    translate_category,
    is_for_single_version,
)
from servicecatalog_factory.template_builder.troposphere_contstants import (
    codebuild as codebuild_troposphere_constants,
)


class PackageTemplateMixin:
    def generate_package_stage(
        self, tpl, item, versions, options, stages, input_artifact_name
    ):
        if self.is_cloudformation_based():
            return self.generate_package_stage_for_cloudformation(
                tpl, item, versions, options, stages, input_artifact_name
            )
        else:
            return self.generate_package_stage_for_non_cloudformation(
                tpl, item, versions, options, stages, input_artifact_name
            )

    def generate_package_stage_for_non_cloudformation(
        self, tpl, item, versions, options, stages, input_artifact_name
    ):
        all_regions = config.get_regions()
        package_stage = stages.get("Package", {})

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
                    Name=f"{base_template.PACKAGE_OUTPUT_ARTIFACT}_{version_name}"
                ),
            )
            secondary_artifacts[f"Package_{version_name}"] = {
                "base-directory": base_directory,
                "files": "**/*",
            }
            count += 1

        environmental_variables = [
            dict(name="TEMPLATE_FORMAT", type="PLAINTEXT", value="yaml",),
            dict(
                name="CATEGORY",
                type="PLAINTEXT",
                value=translate_category(self.category),
            ),
            dict(name="PROVISIONER", type="PLAINTEXT", value="cloudformation",),
            dict(name="ACCOUNT_ID", type="PLAINTEXT", value="${AWS::AccountId}",),
            dict(name="STACK_NAME", type="PLAINTEXT", value="${AWS::StackName}",),
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
            # dict(name="ALL_REGIONS", type="PLAINTEXT", value=" ".join(all_regions),),
        ]

        if package_stage.get("BuildSpec"):
            package_build_spec = package_stage.get("BuildSpec")
            package_build_spec = jinja2.Template(package_build_spec).render(
                ALL_REGIONS=all_regions
            )
        else:
            package_build_spec = self.generate_build_spec(
                item, versions, all_regions, secondary_artifacts, options
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
                    BuildSpec=t.Sub(yaml.safe_dump(package_build_spec)),
                    Type="CODEPIPELINE",
                ),
                Description=t.Sub("package project"),
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
                    ActionTypeId=codebuild_troposphere_constants.ACTION_TYPE_ID_FOR_PACKAGE,
                    Namespace="BuildVariables",
                    OutputArtifacts=output_artifacts,
                    Configuration={
                        "ProjectName": t.Ref("PackageProject"),
                        "PrimarySource": input_artifacts[0].Name,
                        "EnvironmentVariables": t.Sub(
                            json.dumps(environmental_variables)
                        ),
                    },
                )
            ],
        )

    def generate_build_spec(
        self, item, versions, all_regions, secondary_artifacts, options
    ):
        if self.is_cloudformation_based():
            return {
                "version": "0.2",
                "phases": {
                    "build": {
                        "commands": [
                            "env",
                            'eval "cd \$$TRIGGERING_TEST"',
                            "pwd",
                            "cd ${SOURCE_PATH}",
                            "pwd",
                        ]
                        + [
                            f"aws cloudformation package --region {region} --template $(pwd)/$CATEGORY.template.$TEMPLATE_FORMAT --s3-bucket sc-factory-artifacts-$ACCOUNT_ID-{region} --s3-prefix $STACK_NAME --output-template-file $CATEGORY.template-{region}.$TEMPLATE_FORMAT"
                            for region in all_regions
                        ]
                        + [f"zip -r $CATEGORY.zip $PWD/*",],
                    },
                },
                "artifacts": {
                    "files": ["*", "**/*"],
                    "secondary-artifacts": secondary_artifacts,
                },
            }
        else:
            if is_for_single_version(versions):
                version = versions[0]
                source_path = item.get("Source", {}).get(
                    "Path", version.get("Source", {}).get("Path", ".")
                )
                return {
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
                        "build": {
                            "commands": [
                                "env",
                                f"export TRIGGERING_SOURCE=CODEBUILD_SRC_DIR",
                                f"export NAME={item.get('Name')}",
                                f"export VERSION={version.get('Name')}",
                                f"export SOURCE_PATH={source_path}",
                                "cd $SOURCE_PATH",
                                "pwd",
                                f"echo '{json.dumps(utils.unwrap(options))}' > options.json",
                                f"zip -r $CATEGORY.zip $PWD/*",
                            ]
                        },
                    },
                    "artifacts": {"files": ["*", "**/*"],},
                }
            else:

                common_commands = list()
                input_artifacts = list()
                count = 0
                common_commands.append("env")
                item_name = item.get("Name")
                for version in versions:
                    version_name = version.get("Name")
                    triggering_source = (
                        "CODEBUILD_SRC_DIR"
                        if count == 0
                        else f"CODEBUILD_SRC_DIR_Package_{version_name}"
                    )
                    base_directory_path = (
                        "CODEBUILD_SRC_DIR"
                        if count == 0
                        else f"CODEBUILD_SRC_DIR_Validate_{version_name}"
                    )
                    base_directory = f"${base_directory_path}"
                    input_artifacts.append(
                        codepipeline.InputArtifacts(Name=f"Validate_{version_name}"),
                    )
                    path = version.get("Source", {}).get("Path", ".")
                    common_commands.append(
                        f'echo "{triggering_source}" > {base_directory}/triggering_source.txt'
                    )
                    common_commands.append(f'echo "{path}" > {base_directory}/path.txt')
                    common_commands.append(
                        f'echo "{item_name}" > {base_directory}/item_name.txt'
                    )
                    common_commands.append(
                        f'echo "{version_name}" > {base_directory}/version_name.txt'
                    )
                    count += 1

                return {
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
                                "pwd",
                                "export TRIGGERING_SOURCE_PATH=$(servicecatalog-factory print-source-directory ${AWS::StackName}-pipeline $PIPELINE_EXECUTION_ID)",
                                'eval "cd $TRIGGERING_SOURCE_PATH"',
                                "pwd",
                                "export TRIGGERING_SOURCE=$(cat triggering_source.txt)",
                                "export NAME=$(cat item_name.txt)",
                                "export VERSION=$(cat version_name.txt)",
                                "export SOURCE_PATH=$(cat path.txt)",
                                "cd $SOURCE_PATH",
                                "pwd",
                                f"echo '{json.dumps(utils.unwrap(options))}' > options.json",
                                f"zip -r $CATEGORY.zip $PWD/*",
                            ]
                        },
                    },
                    "artifacts": {
                        "files": ["*", "**/*"],
                        "secondary-artifacts": secondary_artifacts,  # EPF
                    },
                }

    def generate_package_stage_for_cloudformation(
        self, tpl, item, versions, options, stages, input_artifact_name
    ):
        all_regions = config.get_regions()
        package_stage = stages.get("Package", {})

        input_artifacts = list()
        output_artifacts = list()
        secondary_artifacts = dict()
        count = 0
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

        if package_stage.get("BuildSpec"):
            package_build_spec = package_stage.get("BuildSpec")
            package_build_spec = jinja2.Template(package_build_spec).render(
                ALL_REGIONS=all_regions
            )
        else:
            package_build_spec = self.generate_build_spec(
                item, versions, all_regions, secondary_artifacts, options
            )
            package_build_spec = yaml.safe_dump(package_build_spec)

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
                Description=t.Sub("package project"),
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
                    ActionTypeId=codebuild_troposphere_constants.ACTION_TYPE_ID_FOR_PACKAGE,
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
                                        value=translate_category(self.category),
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
                                        name="TRIGGERING_TEST",
                                        type="PLAINTEXT",
                                        value="#{BuildVariables.TRIGGERING_TEST}",
                                    ),
                                    dict(
                                        name="SOURCE_PATH",
                                        type="PLAINTEXT",
                                        value="#{BuildVariables.SOURCE_PATH}",
                                    ),
                                    # dict(
                                    #     name="ALL_REGIONS",
                                    #     type="PLAINTEXT",
                                    #     value=" ".join(all_regions),
                                    # ),
                                ]
                            )
                        ),
                    },
                )
            ],
        )
