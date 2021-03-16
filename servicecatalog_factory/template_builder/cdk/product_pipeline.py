import troposphere as t

from troposphere import codepipeline
from servicecatalog_factory.template_builder.base_template import (
    BaseTemplate,
    SOURCE_OUTPUT_ARTIFACT,
    BUILD_OUTPUT_ARTIFACT,
)
import json

from servicecatalog_factory.template_builder.cdk.shared_resources import CDK_BUILD_PROJECT_NAME


class CDK100Template(BaseTemplate):
    def render(self, template, name, version, source, product_ids_by_region, tags, friendly_uid) -> str:
        description = f"{friendly_uid}-{version}"
        tpl = t.Template(Description=description)

        all_regions = product_ids_by_region.keys()

        source_stage = codepipeline.Stages(
            Name="Source",
            Actions=[
                dict(
                    codecommit=codepipeline.Actions(
                        RunOrder=1,
                        RoleArn=t.Sub("arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/SourceRole"),
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
                        RoleArn=t.Sub("arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/SourceRole"),
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
                    Name=template.get("Name"),
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
                        "ProjectName": CDK_BUILD_PROJECT_NAME,
                        "PrimarySource": SOURCE_OUTPUT_ARTIFACT,
                        "EnvironmentVariables": t.Sub(json.dumps([
                            dict(name="NAME",value=name,type="PLAINTEXT"),
                            dict(name="VERSION",value=version,type="PLAINTEXT"),
                        ]))
                    },
                    RunOrder=1,
                )
            ],
        )

        # package_stage = codepipeline.Stages(Name="Package", Actions=[])
        #
        # deploy_stage = codepipeline.Stages(Name="Deploy", Actions=[])

        pipeline = tpl.add_resource(
            codepipeline.Pipeline(
                "Pipeline",
                RoleArn=t.Sub("arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/CodePipelineRole"),
                Stages=[source_stage, build_stage],
                # Stages=[source_stage, build_stage, package_stage, deploy_stage],
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
