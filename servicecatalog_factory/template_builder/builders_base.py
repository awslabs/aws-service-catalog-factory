#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import json

import troposphere as t
from servicecatalog_factory import constants
from troposphere import codepipeline
from troposphere import codebuild
from servicecatalog_factory.template_builder import base_template


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

    def get_source_action_for_source(self, source, source_name_suffix=""):
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
                    Category="Source",
                    Owner="AWS",
                    Version="1",
                    Provider="CodeCommit",
                ),
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
            ),
            github=codepipeline.Actions(
                **common_args,
                ActionTypeId=codepipeline.ActionTypeId(
                    Category="Source",
                    Owner="ThirdParty",
                    Version="1",
                    Provider="GitHub",
                ),
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
            ),
            s3=codepipeline.Actions(
                **common_args,
                ActionTypeId=codepipeline.ActionTypeId(
                    Category="Source",
                    Owner="AWS",
                    Version="1",
                    Provider="S3",
                ),
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

    def build_source_stage(self, tpl, stages, source):
        self.add_custom_provider_details_to_tpl(source, tpl)

        stages.append(
            codepipeline.Stages(
                Name="Source",
                Actions=[
                    self.get_source_action_for_source(source)
                ],
            ),
        )

    def add_custom_provider_details_to_tpl(self, source, tpl):
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


