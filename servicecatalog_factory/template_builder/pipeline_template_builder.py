#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import json

import troposphere as t
import yaml
import jinja2
from deepmerge import always_merger
from troposphere import codepipeline, codebuild

from servicecatalog_factory import config, utils
from servicecatalog_factory import constants
from servicecatalog_factory.template_builder import base_template, shared_resources
from servicecatalog_factory.template_builder.troposphere_contstants import (
    codebuild as codebuild_troposphere_constants,
)


def get_source_action_for_source(source, source_name_suffix=""):
    common_args = dict(
        Name=f"Source{source_name_suffix}",
        RunOrder=1,
        OutputArtifacts=[
            codepipeline.OutputArtifacts(
                Name=f"{base_template.SOURCE_OUTPUT_ARTIFACT}{source_name_suffix}"
            )
        ],
    )
    return dict(
        codecommit=codepipeline.Actions(
            **common_args,
            RoleArn=t.Sub(
                "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/SourceRole"
            ),
            ActionTypeId=codepipeline.ActionTypeId(
                Category="Source", Owner="AWS", Version="1", Provider="CodeCommit",
            ),
            Configuration={
                "RepositoryName": source.get("Configuration").get("RepositoryName"),
                "BranchName": source.get("Configuration").get("BranchName"),
                "PollForSourceChanges": source.get("Configuration").get(
                    "PollForSourceChanges", True
                ),
            },
        ),
        github=codepipeline.Actions(
            **common_args,
            ActionTypeId=codepipeline.ActionTypeId(
                Category="Source", Owner="ThirdParty", Version="1", Provider="GitHub",
            ),
            Configuration={
                "Owner": source.get("Configuration").get("Owner"),
                "Repo": source.get("Configuration").get("Repo"),
                "Branch": source.get("Configuration").get("Branch"),
                "OAuthToken": t.Join(
                    "",
                    [
                        "{{resolve:secretsmanager:",
                        source.get("Configuration").get("SecretsManagerSecret"),
                        ":SecretString:OAuthToken}}",
                    ],
                ),
                "PollForSourceChanges": source.get("Configuration").get(
                    "PollForSourceChanges"
                ),
            },
        ),
        codestarsourceconnection=codepipeline.Actions(
            **common_args,
            RoleArn=t.Sub(
                "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/SourceRole"
            ),
            ActionTypeId=codepipeline.ActionTypeId(
                Category="Source",
                Owner="AWS",
                Version="1",
                Provider="CodeStarSourceConnection",
            ),
            Configuration={
                "ConnectionArn": source.get("Configuration").get("ConnectionArn"),
                "FullRepositoryId": source.get("Configuration").get("FullRepositoryId"),
                "BranchName": source.get("Configuration").get("BranchName"),
                "OutputArtifactFormat": source.get("Configuration").get(
                    "OutputArtifactFormat"
                ),
            },
        ),
        s3=codepipeline.Actions(
            **common_args,
            ActionTypeId=codepipeline.ActionTypeId(
                Category="Source", Owner="AWS", Version="1", Provider="S3",
            ),
            Configuration={
                "S3Bucket": t.Sub(
                    source.get("Configuration").get(
                        "S3Bucket", source.get("Configuration").get("BucketName"),
                    )
                ),
                "S3ObjectKey": t.Sub(source.get("Configuration").get("S3ObjectKey")),
                "PollForSourceChanges": source.get("Configuration").get(
                    "PollForSourceChanges", True
                ),
            },
        ),
        custom=codepipeline.Actions(
            **common_args,
            ActionTypeId=codepipeline.ActionTypeId(
                Category="Source",
                Owner="Custom",
                Version=source.get("Configuration", {}).get(
                    "CustomActionTypeVersion", "CustomVersion1"
                ),
                Provider=source.get("Configuration", {}).get(
                    "CustomActionTypeProvider", "CustomProvider1"
                ),
            ),
            Configuration={
                "GitUrl": source.get("Configuration").get("GitUrl"),
                "Branch": source.get("Configuration").get("Branch"),
                "PipelineName": t.Sub("${AWS::StackName}-pipeline"),
            },
        ),
    ).get(source.get("Provider", "").lower())


def add_custom_provider_details_to_tpl(source, tpl):
    if source.get("Provider", "").lower() == "custom":
        if source.get("Configuration").get("GitWebHookIpAddress") is not None:
            webhook = codepipeline.Webhook(
                "Webhook",
                Authentication="IP",
                TargetAction="Source",
                AuthenticationConfiguration=codepipeline.WebhookAuthConfiguration(
                    AllowedIPRange=source.get("Configuration").get(
                        "GitWebHookIpAddress"
                    )
                ),
                Filters=[
                    codepipeline.WebhookFilterRule(
                        JsonPath="$.changes[0].ref.id",
                        MatchEquals="refs/heads/{Branch}",
                    )
                ],
                TargetPipelineVersion=1,
                TargetPipeline=t.Sub("${AWS::StackName}-pipeline"),
            )
            tpl.add_resource(webhook)
            values_for_sub = {
                "GitUrl": source.get("Configuration").get("GitUrl"),
                "WebhookUrl": t.GetAtt(webhook, "Url"),
            }
        else:
            values_for_sub = {
                "GitUrl": source.get("Configuration").get("GitUrl"),
                "WebhookUrl": "GitWebHookIpAddress was not defined in manifests Configuration",
            }
        output_to_add = t.Output("WebhookUrl")
        output_to_add.Value = t.Sub("${GitUrl}||${WebhookUrl}", **values_for_sub)
        output_to_add.Export = t.Export(t.Sub("${AWS::StackName}-pipeline"))
        tpl.add_output(output_to_add)


def translate_category(category):
    return category.replace("products", "product")


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
                else f"$CODEBUILD_SRC_DIR_Source_{version_name}"
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
                            'eval "cd \$$TRIGGERING_SOURCE"',
                            "pwd",
                            "cd ${SOURCE_PATH}",
                            "pwd",
                        ]
                        + [
                            f"aws cloudformation package --region {region} --template $(pwd)/$CATEGORY.template.$TEMPLATE_FORMAT --s3-bucket sc-factory-artifacts-$ACCOUNT_ID-{region} --s3-prefix $STACK_NAME --output-template-file $CATEGORY.template-{region}.$TEMPLATE_FORMAT"
                            for region in all_regions
                        ],
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
                        else f"CODEBUILD_SRC_DIR_Source_{version_name}"
                    )
                    base_directory = f"${base_directory_path}"
                    input_artifacts.append(
                        codepipeline.InputArtifacts(Name=f"Source_{version_name}"),
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


def is_for_single_version(versions):
    return len(versions) == 1


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
            ['eval "cd \$$TRIGGERING_SOURCE"', "pwd", "cd ${SOURCE_PATH}", "pwd",]
        )

        common_commands.extend(
            [
                f"servicecatalog-factory create-or-update-provisioning-artifact-from-codepipeline-id $PIPELINE_NAME $AWS_REGION $PIPELINE_EXECUTION_ID {region}"
                for region in all_regions
            ]
        )
        package_build_spec = yaml.safe_dump(
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
                                            'eval "cd \$$TRIGGERING_SOURCE"',
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


class PipelineTemplate(
    TestTemplateMixin, BuildTemplateMixin, PackageTemplateMixin, DeployTemplateMixin
):
    def __init__(self, category, pipeline_mode) -> None:
        super().__init__()
        self.category = category
        self.pipeline_mode = pipeline_mode

    def build(self, name, item, versions, options, stages) -> t.Template:
        tpl = t.Template()
        pipeline_stages = list()

        build_stage_input_artifact_name = base_template.SOURCE_OUTPUT_ARTIFACT
        test_stage_input_artifact_name = base_template.SOURCE_OUTPUT_ARTIFACT
        package_stage_input_artifact_name = base_template.SOURCE_OUTPUT_ARTIFACT
        deploy_stage_input_artifact_name = base_template.PACKAGE_OUTPUT_ARTIFACT

        pipeline_stages.append(self.generate_source_stage(tpl, item, versions))
        # if self.has_a_parse_stage(options):
        #     pipeline_stages.append(
        #         self.generate_parse_stage()
        #     )
        if self.has_a_build_stage(stages):
            test_stage_input_artifact_name = base_template.BUILD_OUTPUT_ARTIFACT
            package_stage_input_artifact_name = base_template.BUILD_OUTPUT_ARTIFACT

            pipeline_stages.append(
                self.generate_build_stage(
                    tpl, versions, stages, build_stage_input_artifact_name
                )
            )

        if self.has_a_test_stage(stages):
            if self.is_cloudformation_based():
                package_stage_input_artifact_name = (
                    base_template.VALIDATE_OUTPUT_ARTIFACT
                )

            pipeline_stages.append(
                self.generate_test_stage(
                    tpl, item, versions, options, stages, test_stage_input_artifact_name
                )
            )

        pipeline_stages.append(
            self.generate_package_stage(
                tpl, item, versions, options, stages, package_stage_input_artifact_name
            )
        )
        pipeline_stages.append(
            self.generate_deploy_stage(
                tpl, item, versions, stages, deploy_stage_input_artifact_name
            )
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

    def is_cloudformation_based(self):
        return self.category in ["stack", "products", "product"]

    def has_a_parse_stage(self, options):
        if self.is_cloudformation_based():
            return options.get("ShouldParseAsJinja2Template", False)
        return False

    def generate_source_stage(self, tpl, item, versions) -> codepipeline.Stages:
        actions = list()
        for version in versions:
            source = always_merger.merge(
                item.get("Source", {}), version.get("Source", {})
            )
            add_custom_provider_details_to_tpl(source, tpl)
            actions.append(
                get_source_action_for_source(
                    source, source_name_suffix=f'_{version.get("Name")}'
                )
            )
        return codepipeline.Stages(Name="Source", Actions=actions,)
