#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import troposphere as t
from troposphere import codepipeline

from servicecatalog_factory.template_builder import base_template


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
