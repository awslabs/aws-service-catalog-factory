import yaml
from servicecatalog_factory import constants

import troposphere as t

from troposphere import ssm
from troposphere import s3
from troposphere import sns
from troposphere import codepipeline
from troposphere import sqs
from troposphere import iam
from troposphere import codecommit
from troposphere import codebuild


SOURCE_OUTPUT_ARTIFACT = "Source"
BUILD_OUTPUT_ARTIFACT = "Build"


def get_template(version, source, template):
    description = "todo"
    tpl = t.Template(Description=description)

    source_stage = codepipeline.Stages(
        Name="Source",
        Actions=[
            dict(
                codecommit=codepipeline.Actions(
                    RunOrder=1,
                    RoleArn=t.GetAtt("SourceRole", "Arn"),
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
                                source.get("Configuration").get("SecretsManagerSecret"),
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
                    RoleArn=t.GetAtt("SourceRole", "Arn"),
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
                        "S3ObjectKey": source.get("Configuration").get("S3ObjectKey"),
                        "PollForSourceChanges": source.get("Configuration").get(
                            "PollForSourceChanges"
                        ),
                    },
                    Name="Source",
                ),
            ).get(source.get("Provider", "").lower())
        ],
    )

    build_projects = dict(
        CDK={
            "1.0.0": tpl.add_resource(
                codebuild.Project(
                    "CDKbuild100",
                    Name="CDK-Build-1.0.0",
                    ServiceRole=t.Sub(
                        "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/DeliveryCodeRole"
                    ),
                    Tags=t.Tags.from_dict(
                        **{"ServiceCatalogPuppet:Actor": "Framework"}
                    ),
                    Artifacts=codebuild.Artifacts(Type="CODEPIPELINE"),
                    TimeoutInMinutes=60,
                    Environment=codebuild.Environment(
                        ComputeType=template.get("Environment").get(
                            "ComputeType", constants.ENVIRONMENT_COMPUTE_TYPE_DEFAULT
                        ),
                        Image=template.get("Environment").get(
                            "Image", constants.ENVIRONMENT_IMAGE_DEFAULT
                        ),
                        Type=template.get("Environment").get(
                            "Type", constants.ENVIRONMENT_TYPE_DEFAULT
                        ),
                        EnvironmentVariables=[
                            {
                                "Type": "PLAINTEXT",
                                "Name": "STACK_NAME",
                                "Value": t.Sub("${AWS::StackName}"),
                            },
                            {
                                "Type": "PLAINTEXT",
                                "Name": "ACCOUNT_ID",
                                "Value": t.Sub("${AWS::AccountId}"),
                            },
                        ],
                    ),
                    Source=codebuild.Source(
                        BuildSpec=t.Sub(
                            yaml.safe_dump(
                                dict(
                                    version=0.2,
                                    phases=dict(
                                        install={
                                            "runtime-versions": dict(
                                                python="3.7",
                                                nodejs=template.get(
                                                    "runtime-versions", {}
                                                ).get(
                                                    "nodejs",
                                                    constants.BUILDSPEC_RUNTIME_VERSIONS_NODEJS_DEFAULT,
                                                ),
                                            ),
                                            "commands": [
                                                f"pip install {version}"
                                                if "http" in version
                                                else f"pip install aws-service-catalog-puppet=={version}",
                                                "npm run cdk synth -- --output sct-synth-output",
                                            ],
                                        },
                                        build={
                                            "commands": [
                                                f"servicecatalog-factory generate-template {template.get('Name')} {template.get('Version')} . $STACK_NAME > product.template.yaml",
                                            ]
                                        },
                                    ),
                                    artifacts=dict(
                                        name=BUILD_OUTPUT_ARTIFACT, files=["*", "**/*"],
                                    ),
                                )
                            )
                        ),
                        Type="CODEPIPELINE",
                    ),
                    Description=t.Sub("Create a build stage for template CDK 1.0.0"),
                )
            )
        }
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
                    Category="Build", Owner="AWS", Version="1", Provider="CodeBuild",
                ),
                OutputArtifacts=[
                    codepipeline.OutputArtifacts(Name=BUILD_OUTPUT_ARTIFACT)
                ],
                Configuration={
                    "ProjectName": t.Ref(
                        build_projects.get(template.get("Name")).get(
                            template.get("Version")
                        )
                    ),
                    "PrimarySource": SOURCE_OUTPUT_ARTIFACT,
                },
                RunOrder=1,
            )
        ],
    )

    package_stage = codepipeline.Stages(Name="Package", Actions=[])

    deploy_stage = codepipeline.Stages(Name="Deploy", Actions=[])

    pipeline = tpl.add_resource(
        codepipeline.Pipeline(
            "Pipeline",
            RoleArn=t.GetAtt("PipelineRole", "Arn"),
            Stages=[source_stage, build_stage, package_stage, deploy_stage],
            Name=t.Sub("${AWS::StackName}-pipeline"),
            ArtifactStores=[
                codepipeline.ArtifactStoreMap(
                    Region=region,
                    ArtifactStore=codepipeline.ArtifactStore(
                        Type="S3",
                        Location=t.Sub(
                            "sc-puppet-pipeline-artifacts-${AWS::AccountId}-" + region
                        ),
                    ),
                )
                for region in all_regions
            ],
            RestartExecutionOnUpdate=True,
        )
    )
