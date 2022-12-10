#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import json

import troposphere as t
import yaml
from troposphere import codebuild, codepipeline

from servicecatalog_factory import constants
from servicecatalog_factory.template_builder import base_template
from servicecatalog_factory.template_builder.pipeline.utils import translate_category
from servicecatalog_factory.template_builder.troposphere_contstants import (
    codebuild as codebuild_troposphere_constants,
)


class TestTemplateMixin:
    def has_a_test_stage(self, stages):
        return self.is_cloudformation_based() or stages.get("Tests")

    def generate_test_stage_action_for(
        self,
        action_name,
        build_spec,
        common_args,
        test_input_artifact_name,
        tpl,
        versions,
    ):
        tpl.add_resource(
            codebuild.Project(
                f"{action_name}Project",
                Name=t.Sub(f"${{AWS::StackName}}-{action_name}Project"),
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
                            Name="AWS_URL_SUFFIX",
                            Type="PLAINTEXT",
                            Value=t.Ref("AWS::URLSuffix"),
                        ),
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
                    BuildSpec=t.Sub(yaml.safe_dump(build_spec, width=9999,)),
                    Type="CODEPIPELINE",
                ),
                Description=t.Sub(f"Run {action_name}"),
            )
        )
        actions = [
            codepipeline.Actions(
                **common_args,
                Configuration={
                    "ProjectName": t.Ref(f"{action_name}Project"),
                    "PrimarySource": f"{test_input_artifact_name}_{versions[0].get('Name')}",
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
                                    name="PIPELINE_EXECUTION_ID",
                                    value="#{codepipeline.PipelineExecutionId}",
                                    type="PLAINTEXT",
                                ),
                            ]
                        )
                    ),
                },
                Name=action_name,
            )
        ]
        return actions

    def generate_test_stage(
        self, tpl, item, versions, options, stages, input_artifact_name
    ) -> codepipeline.Stages:
        if self.is_cloudformation_based():
            return self.generate_test_stage_for_cloudformation(
                tpl, item, versions, options, stages, input_artifact_name
            )
        else:
            return self.generate_test_stage_for_non_cloudformation(
                tpl, versions, stages, input_artifact_name
            )

    def generate_test_stage_for_non_cloudformation(
        self, tpl, versions, stages, input_artifact_name
    ) -> codepipeline.Stages:
        input_artifacts = list()
        for version in versions:
            version_name = version.get("Name")
            input_artifacts.append(
                codepipeline.InputArtifacts(
                    Name=f"{input_artifact_name}_{version_name}"
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

        custom_test_stages = stages.get("Tests", {})
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
                self.generate_test_stage_action_for(
                    test_stage_name,
                    yaml.safe_load(test_stage_details.get("BuildSpec")),
                    common_args,
                    input_artifact_name,
                    tpl,
                    versions,
                )
            )

        return codepipeline.Stages(Name="Tests", Actions=actions)

    def generate_test_stage_for_cloudformation(
        self, tpl, item, versions, options, stages, input_artifact_name
    ) -> codepipeline.Stages:
        input_artifacts = list()
        output_artifacts = dict(
            Validate=list(), CFNNag=list(), CloudformationRSpec=list(),
        )
        common_commands = list()
        secondary_artifacts = dict(
            Validate=dict(), CFNNag=dict(), CloudformationRSpec=dict(),
        )
        count = 0
        common_commands.append("env")
        item_name = item.get("Name")
        for version in versions:
            version_name = version.get("Name")
            triggering_source = (
                "CODEBUILD_SRC_DIR"
                if count == 0
                else f"CODEBUILD_SRC_DIR_Source_{version_name}"
            )
            triggering_test = (
                "CODEBUILD_SRC_DIR"
                if count == 0
                else f"CODEBUILD_SRC_DIR_Validate_{version_name}"
            )
            triggering_package = (
                "CODEBUILD_SRC_DIR"
                if count == 0
                else f"CODEBUILD_SRC_DIR_Package_{version_name}"
            )
            base_directory_path = (
                "CODEBUILD_SRC_DIR"
                if count == 0
                else f"CODEBUILD_SRC_DIR_Source_{version_name}"
            )
            base_directory = f"${base_directory_path}"
            input_artifacts.append(
                codepipeline.InputArtifacts(
                    Name=f"{input_artifact_name}_{version_name}"
                ),
            )
            output_artifacts["Validate"].append(
                codepipeline.OutputArtifacts(
                    Name=f"{base_template.VALIDATE_OUTPUT_ARTIFACT}_{version_name}"
                ),
            )
            output_artifacts["CFNNag"].append(
                codepipeline.OutputArtifacts(
                    Name=f"{base_template.CFNNAG_OUTPUT_ARTIFACT}_{version_name}"
                ),
            )
            output_artifacts["CloudformationRSpec"].append(
                codepipeline.OutputArtifacts(
                    Name=f"{base_template.CLOUDFORMATION_RSPEC_OUTPUT_ARTIFACT}_{version_name}"
                ),
            )
            path = version.get("Source", {}).get("Path", ".")
            description = version.get("Description", item.get("Description", "Not set"))
            output = base_directory
            common_commands.append(f'echo "{path}" > {output}/path.txt')
            common_commands.append(
                f'echo "{triggering_source}" > {base_directory}/triggering_source.txt'
            )
            common_commands.append(
                f'echo "{triggering_test}" > {base_directory}/triggering_test.txt'
            )
            common_commands.append(
                f'echo "{triggering_package}" > {base_directory}/triggering_package.txt'
            )
            common_commands.append(f'echo "{item_name}" > {output}/item_name.txt')
            common_commands.append(f'echo "{version_name}" > {output}/version_name.txt')
            common_commands.append(
                f'echo "{description}" > {output}/{path}/description.txt'
            )
            secondary_artifacts["Validate"][f"Validate_{version_name}"] = {
                "base-directory": base_directory,
                "files": "**/*",
            }
            secondary_artifacts["CFNNag"][f"CFNNag_{version_name}"] = {
                "base-directory": base_directory,
                "files": "**/*",
            }
            secondary_artifacts["CloudformationRSpec"][
                f"CloudformationRSpec_{version_name}"
            ] = {
                "base-directory": base_directory,
                "files": "**/*",
            }
            count += 1

        common_commands.extend(
            [
                "export TRIGGERING_SOURCE_PATH=$(servicecatalog-factory print-source-directory ${AWS::StackName}-pipeline $PIPELINE_EXECUTION_ID)",
                "cd $TRIGGERING_SOURCE_PATH",
                "pwd",
                "export TRIGGERING_SOURCE=$(cat triggering_source.txt)",
                "export TRIGGERING_TEST=$(cat triggering_test.txt)",
                "export TRIGGERING_PACKAGE=$(cat triggering_package.txt)",
                "export NAME=$(cat item_name.txt)",
                "export VERSION=$(cat version_name.txt)",
                "export SOURCE_PATH=$(cat path.txt)",
                "cd $SOURCE_PATH",
                "pwd",
            ]
        )

        common_args = dict(
            RunOrder=1,
            InputArtifacts=input_artifacts,
            RoleArn=t.Sub(
                "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/SourceRole"
            ),
            ActionTypeId=codebuild_troposphere_constants.ACTION_TYPE_ID_FOR_TEST,
            Namespace="BuildVariables",
            OutputArtifacts=output_artifacts.get("Validate"),
        )
        install_stage = {
            "runtime-versions": dict(python="3.7",),
            "commands": [
                f"pip install {constants.VERSION}"
                if "http" in constants.VERSION
                else f"pip install aws-service-catalog-factory=={constants.VERSION}",
            ],
        }
        actions = self.generate_test_stage_action_for(
            "Validate",
            dict(
                version=0.2,
                env={
                    "variables": {
                        "TRIGGERING_SOURCE": "NOT_SET",
                        "TRIGGERING_TEST": "NOT_SET",
                        "TRIGGERING_PACKAGE": "NOT_SET",
                        "NAME": "NOT_SET",
                        "VERSION": "NOT_SET",
                        "SOURCE_PATH": "NOT_SET",
                    },
                    "exported-variables": [
                        "TRIGGERING_SOURCE",
                        "TRIGGERING_TEST",
                        "TRIGGERING_PACKAGE",
                        "NAME",
                        "VERSION",
                        "SOURCE_PATH",
                    ],
                },
                phases=dict(
                    install=install_stage,
                    build={
                        "commands": common_commands
                        + [
                            "export FactoryTemplateValidateBucket=$(aws cloudformation list-stack-resources --stack-name servicecatalog-factory --query 'StackResourceSummaries[?LogicalResourceId==`FactoryTemplateValidateBucket`].PhysicalResourceId' --output text)",
                            "aws s3 cp $CATEGORY.template.$TEMPLATE_FORMAT s3://$FactoryTemplateValidateBucket/$CODEBUILD_BUILD_ID.$TEMPLATE_FORMAT",
                            "aws cloudformation validate-template --template-url https://$FactoryTemplateValidateBucket.s3.$AWS_REGION.$AWS_URL_SUFFIX/$CODEBUILD_BUILD_ID.$TEMPLATE_FORMAT",
                        ]
                    },
                ),
                artifacts={
                    "files": ["**/*"],
                    "secondary-artifacts": secondary_artifacts.get("Validate"),
                },
            ),
            common_args,
            input_artifact_name,
            tpl,
            versions,
        )

        del common_args["Namespace"]

        if options.get("ShouldCFNNag"):
            common_args["OutputArtifacts"] = output_artifacts.get("CFNNag")
            actions.extend(
                self.generate_test_stage_action_for(
                    "CFNNag",
                    dict(
                        version=0.2,
                        phases=dict(
                            install={
                                "runtime-versions": dict(ruby="2.x", python="3.7",),
                                "commands": [
                                    f"pip install {constants.VERSION}"
                                    if "http" in constants.VERSION
                                    else f"pip install aws-service-catalog-factory=={constants.VERSION}",
                                    "gem install cfn-nag",
                                    "cfn_nag_rules",
                                ],
                            },
                            build={
                                "commands": common_commands
                                + [
                                    "cfn_nag_scan --input-path ./$CATEGORY.template.$TEMPLATE_FORMAT"
                                ]
                            },
                        ),
                        artifacts={
                            "files": ["**/*"],
                            "secondary-artifacts": secondary_artifacts.get("CFNNag"),
                        },
                    ),
                    common_args,
                    input_artifact_name,
                    tpl,
                    versions,
                )
            )

        if options.get("ShouldCloudformationRSpec"):
            common_args["OutputArtifacts"] = output_artifacts.get("CloudformationRSpec")
            actions.extend(
                self.generate_test_stage_action_for(
                    "CloudformationRSpec",
                    dict(
                        version=0.2,
                        phases=dict(
                            install={
                                "runtime-versions": dict(ruby="2.x", python="3.7",),
                                "commands": [
                                    f"pip install {constants.VERSION}"
                                    if "http" in constants.VERSION
                                    else f"pip install aws-service-catalog-factory=={constants.VERSION}",
                                    "gem install cloudformation_rspec",
                                    "gem install rspec_junit_formatter",
                                    "pip install cfn-lint",
                                ],
                            },
                            build={
                                "commands": common_commands
                                + [
                                    "rspec  --format progress --format RspecJunitFormatter --out reports/rspec.xml specs/",
                                ]
                            },
                        ),
                        reports=dict(
                            junit={
                                "files": ["*", "**/*"],
                                "base-directory": "reports",
                                "file-format": "JUNITXML",
                            },
                        ),
                        artifacts={
                            "files": ["**/*"],
                            "secondary-artifacts": secondary_artifacts.get(
                                "CloudformationRSpec"
                            ),
                        },
                    ),
                    common_args,
                    input_artifact_name,
                    tpl,
                    versions,
                )
            )

        custom_test_stages = stages.get("Tests", {})
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
                self.generate_test_stage_action_for(
                    test_stage_name,
                    yaml.safe_load(test_stage_details.get("BuildSpec")),
                    common_args,
                    input_artifact_name,
                    tpl,
                    versions,
                )
            )

        return codepipeline.Stages(Name="Tests", Actions=actions)
