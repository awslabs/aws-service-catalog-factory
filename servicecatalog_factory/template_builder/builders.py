#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import json

import troposphere as t
import yaml
import jinja2

from servicecatalog_factory import utils
from servicecatalog_factory import config
from servicecatalog_factory import constants
from troposphere import codepipeline
from troposphere import codebuild
from servicecatalog_factory.template_builder import base_template
from servicecatalog_factory.template_builder import shared_resources


class BaseTemplateBuilder:
    def add_custom_tests(self, tpl, stages, actions, test_input_artifact_name):
        for test_action_name, test_action_details in stages.get("Tests", {}).items():
            project = tpl.add_resource(
                codebuild.Project(
                    test_action_name,
                    Name=t.Sub("${AWS::StackName}-" + test_action_name),
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
                        Image=test_action_details.get(
                            "BuildSpecImage", constants.ENVIRONMENT_IMAGE_DEFAULT
                        ),
                        Type=constants.ENVIRONMENT_TYPE_DEFAULT,
                        EnvironmentVariables=[
                            codebuild.EnvironmentVariable(
                                Name="TEMPLATE_FORMAT", Type="PLAINTEXT", Value="yaml",
                            ),
                            codebuild.EnvironmentVariable(
                                Name="CATEGORY", Type="PLAINTEXT", Value="stack",
                            ),
                        ],
                    ),
                    Source=codebuild.Source(
                        BuildSpec=test_action_details.get("BuildSpec"),
                        Type="CODEPIPELINE",
                    ),
                    Description=t.Sub(test_action_name + " for ${AWS::StackName}"),
                )
            )

            actions.append(
                codepipeline.Actions(
                    RunOrder=1,
                    RoleArn=t.Sub(
                        "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/SourceRole"
                    ),
                    InputArtifacts=[
                        codepipeline.InputArtifacts(Name=test_input_artifact_name),
                    ],
                    ActionTypeId=codepipeline.ActionTypeId(
                        Category="Test", Owner="AWS", Version="1", Provider="CodeBuild",
                    ),
                    OutputArtifacts=[
                        codepipeline.OutputArtifacts(Name=test_action_name)
                    ],
                    Configuration={
                        "ProjectName": t.Ref(project),
                        "PrimarySource": test_input_artifact_name,
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
                                        value="stack",
                                        type="PLAINTEXT",
                                    ),
                                ]
                            )
                        ),
                    },
                    Name=test_action_name,
                )
            )

    def build_source_stage(self, tpl, stages, source):
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

        stages.append(
            codepipeline.Stages(
                Name="Source",
                Actions=[
                    dict(
                        codecommit=codepipeline.Actions(
                            RunOrder=1,
                            RoleArn=t.Sub(
                                "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/SourceRole"
                            ),
                            ActionTypeId=codepipeline.ActionTypeId(
                                Category="Source",
                                Owner="AWS",
                                Version="1",
                                Provider="CodeCommit",
                            ),
                            OutputArtifacts=[
                                codepipeline.OutputArtifacts(
                                    Name=base_template.SOURCE_OUTPUT_ARTIFACT
                                )
                            ],
                            Configuration={
                                "RepositoryName": source.get("Configuration").get(
                                    "RepositoryName"
                                ),
                                "BranchName": source.get("Configuration").get(
                                    "BranchName"
                                ),
                                "PollForSourceChanges": source.get("Configuration").get(
                                    "PollForSourceChanges", True
                                ),
                            },
                            Name="Source",
                        ),
                        github=codepipeline.Actions(
                            RunOrder=1,
                            ActionTypeId=codepipeline.ActionTypeId(
                                Category="Source",
                                Owner="ThirdParty",
                                Version="1",
                                Provider="GitHub",
                            ),
                            OutputArtifacts=[
                                codepipeline.OutputArtifacts(
                                    Name=base_template.SOURCE_OUTPUT_ARTIFACT
                                )
                            ],
                            Configuration={
                                "Owner": source.get("Configuration").get("Owner"),
                                "Repo": source.get("Configuration").get("Repo"),
                                "Branch": source.get("Configuration").get("Branch"),
                                "OAuthToken": t.Join(
                                    "",
                                    [
                                        "{{resolve:secretsmanager:",
                                        source.get("Configuration").get(
                                            "SecretsManagerSecret"
                                        ),
                                        ":SecretString:OAuthToken}}",
                                    ],
                                ),
                                "PollForSourceChanges": source.get("Configuration").get(
                                    "PollForSourceChanges"
                                ),
                            },
                            Name="Source",
                        ),
                        codestarsourceconnection=codepipeline.Actions(
                            RunOrder=1,
                            RoleArn=t.Sub(
                                "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/SourceRole"
                            ),
                            ActionTypeId=codepipeline.ActionTypeId(
                                Category="Source",
                                Owner="AWS",
                                Version="1",
                                Provider="CodeStarSourceConnection",
                            ),
                            OutputArtifacts=[
                                codepipeline.OutputArtifacts(
                                    Name=base_template.SOURCE_OUTPUT_ARTIFACT
                                )
                            ],
                            Configuration={
                                "ConnectionArn": source.get("Configuration").get(
                                    "ConnectionArn"
                                ),
                                "FullRepositoryId": source.get("Configuration").get(
                                    "FullRepositoryId"
                                ),
                                "BranchName": source.get("Configuration").get(
                                    "BranchName"
                                ),
                                "OutputArtifactFormat": source.get("Configuration").get(
                                    "OutputArtifactFormat"
                                ),
                            },
                            Name="Source",
                        ),
                        s3=codepipeline.Actions(
                            RunOrder=1,
                            ActionTypeId=codepipeline.ActionTypeId(
                                Category="Source",
                                Owner="AWS",
                                Version="1",
                                Provider="S3",
                            ),
                            OutputArtifacts=[
                                codepipeline.OutputArtifacts(
                                    Name=base_template.SOURCE_OUTPUT_ARTIFACT
                                )
                            ],
                            Configuration={
                                "S3Bucket": t.Sub(
                                    source.get("Configuration").get(
                                        "S3Bucket",
                                        source.get("Configuration").get("BucketName"),
                                    )
                                ),
                                "S3ObjectKey": t.Sub(
                                    source.get("Configuration").get("S3ObjectKey")
                                ),
                                "PollForSourceChanges": source.get("Configuration").get(
                                    "PollForSourceChanges", True
                                ),
                            },
                            Name="Source",
                        ),
                        custom=codepipeline.Actions(
                            RunOrder=1,
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
                            OutputArtifacts=[
                                codepipeline.OutputArtifacts(
                                    Name=base_template.SOURCE_OUTPUT_ARTIFACT
                                )
                            ],
                            Configuration={
                                "GitUrl": source.get("Configuration").get("GitUrl"),
                                "Branch": source.get("Configuration").get("Branch"),
                                "PipelineName": t.Sub("${AWS::StackName}-pipeline"),
                            },
                            Name="Source",
                        ),
                    ).get(source.get("Provider", "").lower())
                ],
            ),
        )


class StackTemplateBuilder(BaseTemplateBuilder):
    def build_test_stage(self, test_input_artifact_name, options, tpl, stages, source):
        actions = [
            codepipeline.Actions(
                RunOrder=1,
                RoleArn=t.Sub(
                    "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/SourceRole"
                ),
                InputArtifacts=[
                    codepipeline.InputArtifacts(Name=test_input_artifact_name),
                ],
                ActionTypeId=codepipeline.ActionTypeId(
                    Category="Test", Owner="AWS", Version="1", Provider="CodeBuild",
                ),
                OutputArtifacts=[
                    codepipeline.OutputArtifacts(
                        Name=base_template.VALIDATE_OUTPUT_ARTIFACT
                    )
                ],
                Configuration={
                    "ProjectName": shared_resources.VALIDATE_PROJECT_NAME,
                    "PrimarySource": test_input_artifact_name,
                    "EnvironmentVariables": t.Sub(
                        json.dumps(
                            [
                                dict(
                                    name="TEMPLATE_FORMAT",
                                    value="yaml",
                                    type="PLAINTEXT",
                                ),
                                dict(name="CATEGORY", value="stack", type="PLAINTEXT",),
                                dict(
                                    name="SOURCE_PATH",
                                    value=source.get("Path", "."),
                                    type="PLAINTEXT",
                                ),
                            ]
                        )
                    ),
                },
                Name="Validate",
            )
        ]

        if options.get("ShouldCFNNag"):
            actions.append(
                codepipeline.Actions(
                    RunOrder=1,
                    RoleArn=t.Sub(
                        "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/SourceRole"
                    ),
                    InputArtifacts=[
                        codepipeline.InputArtifacts(Name=test_input_artifact_name),
                    ],
                    ActionTypeId=codepipeline.ActionTypeId(
                        Category="Test", Owner="AWS", Version="1", Provider="CodeBuild",
                    ),
                    OutputArtifacts=[
                        codepipeline.OutputArtifacts(
                            Name=base_template.CFNNAG_OUTPUT_ARTIFACT
                        )
                    ],
                    Configuration={
                        "ProjectName": shared_resources.CFNNAG_PROJECT_NAME,
                        "PrimarySource": test_input_artifact_name,
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
                                        value="stack",
                                        type="PLAINTEXT",
                                    ),
                                    dict(
                                        name="SOURCE_PATH",
                                        value=source.get("Path", "."),
                                        type="PLAINTEXT",
                                    ),
                                ]
                            )
                        ),
                    },
                    Name="CFNNag",
                )
            )

        if options.get("ShouldCloudformationRSpec"):
            actions.append(
                codepipeline.Actions(
                    RunOrder=1,
                    RoleArn=t.Sub(
                        "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/SourceRole"
                    ),
                    InputArtifacts=[
                        codepipeline.InputArtifacts(Name=test_input_artifact_name),
                    ],
                    ActionTypeId=codepipeline.ActionTypeId(
                        Category="Test", Owner="AWS", Version="1", Provider="CodeBuild",
                    ),
                    OutputArtifacts=[
                        codepipeline.OutputArtifacts(
                            Name=base_template.CLOUDFORMATION_RSPEC_OUTPUT_ARTIFACT
                        )
                    ],
                    Configuration={
                        "ProjectName": shared_resources.RSPEC_PROJECT_NAME,
                        "PrimarySource": test_input_artifact_name,
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
                                        value="stack",
                                        type="PLAINTEXT",
                                    ),
                                    dict(
                                        name="SOURCE_PATH",
                                        value=source.get("Path", "."),
                                        type="PLAINTEXT",
                                    ),
                                ]
                            )
                        ),
                    },
                    Name="CloudFormationRSpec",
                )
            )

        self.add_custom_tests(tpl, stages, actions, test_input_artifact_name)

        stage = codepipeline.Stages(Name="Tests", Actions=actions)

        return stage

    def build(self, name, version, source, options, stages):
        all_regions = config.get_regions()
        factory_version = constants.VERSION
        template_description = f'{{"version": "{factory_version}", "framework": "servicecatalog-factory", "role": "product-pipeline", "type": "cloudformation", "category": "stack"}}'
        tpl = t.Template(Description=template_description)

        build_input_artifact_name = base_template.SOURCE_OUTPUT_ARTIFACT
        test_input_artifact_name = base_template.SOURCE_OUTPUT_ARTIFACT
        package_input_artifact_name = base_template.SOURCE_OUTPUT_ARTIFACT

        if options.get("ShouldParseAsJinja2Template"):
            build_input_artifact_name = base_template.PARSE_OUTPUT_ARTIFACT
            test_input_artifact_name = base_template.PARSE_OUTPUT_ARTIFACT
            package_input_artifact_name = base_template.PARSE_OUTPUT_ARTIFACT

        if stages.get("Build", {}).get("BuildSpec"):
            test_input_artifact_name = base_template.BUILD_OUTPUT_ARTIFACT
            package_input_artifact_name = base_template.BUILD_OUTPUT_ARTIFACT

        deploy_input_artifact_name = "Package"

        pipeline_stages = []

        self.build_source_stage(tpl, pipeline_stages, source)

        if options.get("ShouldParseAsJinja2Template"):
            pipeline_stages.append(
                codepipeline.Stages(
                    Name="Parse",
                    Actions=[
                        codepipeline.Actions(
                            RunOrder=1,
                            RoleArn=t.Sub(
                                "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/SourceRole"
                            ),
                            InputArtifacts=[
                                codepipeline.InputArtifacts(
                                    Name=base_template.SOURCE_OUTPUT_ARTIFACT
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
                                    Name=base_template.PARSE_OUTPUT_ARTIFACT
                                )
                            ],
                            Configuration={
                                "ProjectName": shared_resources.JINJA_PROJECT_NAME,
                                "PrimarySource": base_template.SOURCE_OUTPUT_ARTIFACT,
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
                                                value="stack",
                                                type="PLAINTEXT",
                                            ),
                                            dict(
                                                name="SOURCE_PATH",
                                                value=source.get("Path", "."),
                                                type="PLAINTEXT",
                                            ),
                                        ]
                                    )
                                ),
                            },
                            Name="Source",
                        )
                    ],
                )
            )

        if stages.get("Build", {}).get("BuildSpec"):
            tpl.add_resource(
                codebuild.Project(
                    "BuildProject",
                    Name=t.Sub("${AWS::StackName}-BuildProject"),
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
                        Image=stages.get("Build", {}).get(
                            "BuildSpecImage", constants.ENVIRONMENT_IMAGE_DEFAULT
                        ),
                        Type=constants.ENVIRONMENT_TYPE_DEFAULT,
                        PrivilegedMode=stages.get("Build", {}).get(
                            "PrivilegedMode",
                            constants.GENERIC_BUILD_PROJECT_PRIVILEGED_MODE_DEFAULT,
                        ),
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
                        BuildSpec=stages.get("Build", {}).get("BuildSpec"),
                        Type="CODEPIPELINE",
                    ),
                    Description=t.Sub("build project"),
                )
            )

            pipeline_stages.append(
                codepipeline.Stages(
                    Name="Build",
                    Actions=[
                        codepipeline.Actions(
                            Name="Build",
                            RunOrder=1,
                            RoleArn=t.Sub(
                                "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/SourceRole"
                            ),
                            InputArtifacts=[
                                codepipeline.InputArtifacts(
                                    Name=build_input_artifact_name
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
                                    Name=base_template.BUILD_OUTPUT_ARTIFACT
                                )
                            ],
                            Configuration={
                                "ProjectName": t.Sub("${AWS::StackName}-BuildProject"),
                                "PrimarySource": build_input_artifact_name,
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
                                                value="stack",
                                                type="PLAINTEXT",
                                            ),
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

        pipeline_stages.append(
            self.build_test_stage(
                test_input_artifact_name, options, tpl, stages, source
            )
        )

        if stages.get("Package", {}).get("BuildSpec"):
            package_build_spec = stages.get("Package", {}).get("BuildSpec")
            package_build_spec = jinja2.Template(package_build_spec).render(
                ALL_REGIONS=all_regions
            )
        else:
            package_build_spec = yaml.safe_dump(
                {
                    "version": "0.2",
                    "phases": {
                        "install": {"runtime-versions": {"python": "3.8"}},
                        "build": {
                            "commands": ["cd $SOURCE_PATH",]
                            + [
                                f"aws cloudformation package --region {region} --template $(pwd)/$CATEGORY.template.$TEMPLATE_FORMAT --s3-bucket sc-factory-artifacts-$ACCOUNT_ID-{region} --s3-prefix $STACK_NAME --output-template-file $CATEGORY.template-{region}.$TEMPLATE_FORMAT"
                                for region in all_regions
                            ],
                        },
                    },
                    "artifacts": {"files": ["*", "**/*"],},
                }
            )

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
                            Name="TEMPLATE_FORMAT", Type="PLAINTEXT", Value="yaml",
                        ),
                        codebuild.EnvironmentVariable(
                            Name="CATEGORY", Type="PLAINTEXT", Value="stack",
                        ),
                        codebuild.EnvironmentVariable(
                            Name="ACCOUNT_ID",
                            Type="PLAINTEXT",
                            Value=t.Sub("${AWS::AccountId}"),
                        ),
                        codebuild.EnvironmentVariable(
                            Name="STACK_NAME",
                            Type="PLAINTEXT",
                            Value=t.Sub("${AWS::StackName}"),
                        ),
                        codebuild.EnvironmentVariable(
                            Name="SOURCE_PATH", Type="PLAINTEXT", Value=".",
                        ),
                        codebuild.EnvironmentVariable(
                            Name="ALL_REGIONS",
                            Type="PLAINTEXT",
                            Value=" ".join(all_regions),
                        ),
                    ],
                ),
                Source=codebuild.Source(
                    BuildSpec=package_build_spec, Type="CODEPIPELINE",
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
                                            name="TEMPLATE_FORMAT",
                                            value="yaml",
                                            type="PLAINTEXT",
                                        ),
                                        dict(
                                            name="CATEGORY",
                                            value="stack",
                                            type="PLAINTEXT",
                                        ),
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
                            Name="CATEGORY", Type="PLAINTEXT", Value="stack",
                        ),
                        codebuild.EnvironmentVariable(
                            Name="ACCOUNT_ID",
                            Type="PLAINTEXT",
                            Value=t.Sub("${AWS::AccountId}"),
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
                                        f'aws s3 cp . s3://sc-puppet-stacks-repository-$ACCOUNT_ID/$CATEGORY/{name}/{version}/ --recursive --exclude "*" --include "$CATEGORY.template.$TEMPLATE_FORMAT" --include "$CATEGORY.template-*.$TEMPLATE_FORMAT"',
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
                                Name=deploy_input_artifact_name
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
                        Configuration={
                            "ProjectName": deploy_project_name,
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
                                            value="stack",
                                            type="PLAINTEXT",
                                        ),
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


class NonCFNTemplateBuilder(BaseTemplateBuilder):
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
