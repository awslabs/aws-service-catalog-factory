# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import troposphere as t

from troposphere import codepipeline
from servicecatalog_factory.template_builder.base_template import (
    BaseTemplate,
    SOURCE_OUTPUT_ARTIFACT,
    BUILD_OUTPUT_ARTIFACT,
    VALIDATE_OUTPUT_ARTIFACT,
    PACKAGE_OUTPUT_ARTIFACT,
    DEPLOY_OUTPUT_ARTIFACT,
)
import json

from servicecatalog_factory.template_builder import shared_resources

from servicecatalog_factory.template_builder.cdk import (
    shared_resources as cdk_shared_resources,
)


class CDK100Template(BaseTemplate):
    def render(
        self,
        template,
        name,
        version,
        description,
        source,
        product_ids_by_region,
        tags,
        friendly_uid,
    ) -> str:
        template_description = f"{friendly_uid}-{version}"
        tpl = t.Template(Description=template_description)

        all_regions = product_ids_by_region.keys()

        source_stage = codepipeline.Stages(
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
                            codepipeline.OutputArtifacts(Name=SOURCE_OUTPUT_ARTIFACT)
                        ],
                        Configuration={
                            "RepositoryName": source.get("Configuration").get(
                                "RepositoryName"
                            ),
                            "BranchName": source.get("Configuration").get("BranchName"),
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
                            codepipeline.OutputArtifacts(Name=SOURCE_OUTPUT_ARTIFACT)
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
                            codepipeline.OutputArtifacts(Name=SOURCE_OUTPUT_ARTIFACT)
                        ],
                        Configuration={
                            "ConnectionArn": source.get("Configuration").get(
                                "ConnectionArn"
                            ),
                            "FullRepositoryId": source.get("Configuration").get(
                                "FullRepositoryId"
                            ),
                            "BranchName": source.get("Configuration").get("BranchName"),
                            "OutputArtifactFormat": source.get("Configuration").get(
                                "OutputArtifactFormat"
                            ),
                        },
                        Name="Source",
                    ),
                    s3=codepipeline.Actions(
                        RunOrder=1,
                        ActionTypeId=codepipeline.ActionTypeId(
                            Category="Source", Owner="AWS", Version="1", Provider="S3",
                        ),
                        OutputArtifacts=[
                            codepipeline.OutputArtifacts(Name=SOURCE_OUTPUT_ARTIFACT)
                        ],
                        Configuration={
                            "S3Bucket": source.get("Configuration").get("S3Bucket"),
                            "S3ObjectKey": source.get("Configuration").get(
                                "S3ObjectKey"
                            ),
                            "PollForSourceChanges": source.get("Configuration").get(
                                "PollForSourceChanges"
                            ),
                        },
                        Name="Source",
                    ),
                ).get(source.get("Provider", "").lower())
            ],
        )

        build_stage = codepipeline.Stages(
            Name="Build",
            Actions=[
                codepipeline.Actions(
                    InputArtifacts=[
                        codepipeline.InputArtifacts(Name=SOURCE_OUTPUT_ARTIFACT),
                    ],
                    Name=f'{template.get("Name")}-{template.get("Version")}',
                    ActionTypeId=codepipeline.ActionTypeId(
                        Category="Build",
                        Owner="AWS",
                        Version="1",
                        Provider="CodeBuild",
                    ),
                    OutputArtifacts=[
                        codepipeline.OutputArtifacts(Name=BUILD_OUTPUT_ARTIFACT)
                    ],
                    Configuration={
                        "ProjectName": cdk_shared_resources.CDK_BUILD_PROJECT_NAME,
                        "PrimarySource": SOURCE_OUTPUT_ARTIFACT,
                        "EnvironmentVariables": t.Sub(
                            json.dumps(
                                [
                                    dict(name="NAME", value=name, type="PLAINTEXT"),
                                    dict(
                                        name="VERSION", value=version, type="PLAINTEXT"
                                    ),
                                ]
                            )
                        ),
                    },
                    RunOrder=1,
                )
            ],
        )

        validate_stage = codepipeline.Stages(
            Name="Validate",
            Actions=[
                codepipeline.Actions(
                    InputArtifacts=[
                        codepipeline.InputArtifacts(Name=BUILD_OUTPUT_ARTIFACT),
                    ],
                    Name="Validate",
                    ActionTypeId=codepipeline.ActionTypeId(
                        Category="Test", Owner="AWS", Version="1", Provider="CodeBuild",
                    ),
                    OutputArtifacts=[
                        codepipeline.OutputArtifacts(Name=VALIDATE_OUTPUT_ARTIFACT)
                    ],
                    Configuration={
                        "ProjectName": shared_resources.VALIDATE_PROJECT_NAME,
                        "PrimarySource": BUILD_OUTPUT_ARTIFACT,
                    },
                    RunOrder=1,
                )
            ],
        )
        #
        package_stage = codepipeline.Stages(
            Name="Package",
            Actions=[
                codepipeline.Actions(
                    InputArtifacts=[
                        codepipeline.InputArtifacts(Name=BUILD_OUTPUT_ARTIFACT),
                    ],
                    Name="Package",
                    ActionTypeId=codepipeline.ActionTypeId(
                        Category="Build",
                        Owner="AWS",
                        Version="1",
                        Provider="CodeBuild",
                    ),
                    OutputArtifacts=[
                        codepipeline.OutputArtifacts(Name=PACKAGE_OUTPUT_ARTIFACT)
                    ],
                    Configuration={
                        "ProjectName": cdk_shared_resources.CDK_PACKAGE_PROJECT_NAME,
                        "PrimarySource": BUILD_OUTPUT_ARTIFACT,
                        "EnvironmentVariables": t.Sub(
                            json.dumps(
                                [
                                    dict(name="NAME", value=name, type="PLAINTEXT"),
                                    dict(
                                        name="VERSION", value=version, type="PLAINTEXT"
                                    ),
                                ]
                            )
                        ),
                    },
                    RunOrder=1,
                )
            ],
        )

        deploy_stage = codepipeline.Stages(
            Name="Deploy",
            Actions=[
                codepipeline.Actions(
                    InputArtifacts=[
                        codepipeline.InputArtifacts(Name=PACKAGE_OUTPUT_ARTIFACT),
                    ],
                    Name="Deploy",
                    ActionTypeId=codepipeline.ActionTypeId(
                        Category="Build",
                        Owner="AWS",
                        Version="1",
                        Provider="CodeBuild",
                    ),
                    OutputArtifacts=[
                        codepipeline.OutputArtifacts(Name=DEPLOY_OUTPUT_ARTIFACT)
                    ],
                    Configuration={
                        "ProjectName": cdk_shared_resources.CDK_DEPLOY_PROJECT_NAME,
                        "PrimarySource": PACKAGE_OUTPUT_ARTIFACT,
                        "EnvironmentVariables": t.Sub(
                            json.dumps(
                                [
                                    dict(name="NAME", value=name, type="PLAINTEXT"),
                                    dict(
                                        name="VERSION", value=version, type="PLAINTEXT"
                                    ),
                                    dict(
                                        name="DESCRIPTION",
                                        value=description,
                                        type="PLAINTEXT",
                                    ),
                                ]
                                + [
                                    dict(
                                        name=f"PRODUCT_ID_{region.replace('-', '_')}",
                                        value=product_ids_by_region[region],
                                        type="PLAINTEXT",
                                    )
                                    for region in all_regions
                                ]
                            )
                        ),
                    },
                    RunOrder=1,
                )
            ],
        )

        pipeline = tpl.add_resource(
            codepipeline.Pipeline(
                "Pipeline",
                RoleArn=t.Sub(
                    "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/CodePipelineRole"
                ),
                Stages=[
                    source_stage,
                    build_stage,
                    validate_stage,
                    package_stage,
                    deploy_stage,
                ],
                Name=t.Sub("${AWS::StackName}-pipeline"),
                ArtifactStores=[
                    codepipeline.ArtifactStoreMap(
                        Region=region,
                        ArtifactStore=codepipeline.ArtifactStore(
                            Type="S3",
                            Location=t.Sub(
                                "sc-puppet-pipeline-artifacts-${AWS::AccountId}-"
                                + region
                            ),
                        ),
                    )
                    for region in all_regions
                ],
                RestartExecutionOnUpdate=True,
            )
        )
        return tpl.to_yaml(clean_up=True)
