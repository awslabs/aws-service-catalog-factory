import json

import troposphere as t
import yaml

from servicecatalog_factory import config
from servicecatalog_factory import constants
from troposphere import codepipeline
from troposphere import codebuild
from servicecatalog_factory.template_builder import base_template
from servicecatalog_factory.template_builder import shared_resources


class StackTemplateBuilder:

    def build_source_action(self, source):
        return dict(
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
                    codepipeline.OutputArtifacts(Name=base_template.SOURCE_OUTPUT_ARTIFACT)
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
                    codepipeline.OutputArtifacts(Name=base_template.SOURCE_OUTPUT_ARTIFACT)
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
                    codepipeline.OutputArtifacts(Name=base_template.SOURCE_OUTPUT_ARTIFACT)
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
                    Category="Source",
                    Owner="AWS",
                    Version="1",
                    Provider="S3",
                ),
                OutputArtifacts=[
                    codepipeline.OutputArtifacts(Name=base_template.SOURCE_OUTPUT_ARTIFACT)
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

    def build_test_stage(self, test_input_artifact_name, options):
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
                    Category="Build",
                    Owner="AWS",
                    Version="1",
                    Provider="CodeBuild",
                ),
                OutputArtifacts=[
                    codepipeline.OutputArtifacts(Name=base_template.VALIDATE_OUTPUT_ARTIFACT)
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
                                dict(
                                    name="CATEGORY",
                                    value="stack",
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
                        Category="Build",
                        Owner="AWS",
                        Version="1",
                        Provider="CodeBuild",
                    ),
                    OutputArtifacts=[
                        codepipeline.OutputArtifacts(Name=base_template.CFNNAG_OUTPUT_ARTIFACT)
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
                        Category="Build",
                        Owner="AWS",
                        Version="1",
                        Provider="CodeBuild",
                    ),
                    OutputArtifacts=[
                        codepipeline.OutputArtifacts(Name=base_template.CLOUDFORMATION_RSPEC_OUTPUT_ARTIFACT)
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
                                ]
                            )
                        ),
                    },
                    Name="CloudFormationRSpec",
                )
            )
        stage = codepipeline.Stages(
            Name="Tests",
            Actions=actions
        )

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

        pipeline_stages = [
            codepipeline.Stages(
                Name="Source",
                Actions=[self.build_source_action(source)]
            )
        ]

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
                                codepipeline.InputArtifacts(Name=base_template.SOURCE_OUTPUT_ARTIFACT),
                            ],
                            ActionTypeId=codepipeline.ActionTypeId(
                                Category="Build",
                                Owner="AWS",
                                Version="1",
                                Provider="CodeBuild",
                            ),
                            OutputArtifacts=[
                                codepipeline.OutputArtifacts(Name=base_template.PARSE_OUTPUT_ARTIFACT)
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
                                        ]
                                    )
                                ),
                            },
                            Name="Source",
                        )
                    ]
                )
            )

        if stages.get("Build", {}).get("BuildSpec"):
            tpl.add_resource(
                codebuild.Project(
                    "build_project",
                    Name=t.Sub("${AWS::StackName}-BuildProject"),
                    ServiceRole=t.Sub(
                        "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/DeliveryCodeRole"
                    ),
                    Tags=t.Tags.from_dict(**{"ServiceCatalogPuppet:Actor": "Framework"}),
                    Artifacts=codebuild.Artifacts(Type="CODEPIPELINE"),
                    TimeoutInMinutes=60,
                    Environment=codebuild.Environment(
                        ComputeType=constants.ENVIRONMENT_COMPUTE_TYPE_DEFAULT,
                        Image=stages.get("Build", {}).get("BuildSpecImage", constants.ENVIRONMENT_IMAGE_DEFAULT),
                        Type=constants.ENVIRONMENT_TYPE_DEFAULT,
                        EnvironmentVariables=[
                            codebuild.EnvironmentVariable(
                                Name="TEMPLATE_FORMAT",
                                Type="PLAINTEXT",
                                Value="yaml",
                            ),
                            codebuild.EnvironmentVariable(
                                Name="CATEGORY",
                                Type="PLAINTEXT",
                                Value="stack",
                            ),
                        ],
                    ),
                    Source=codebuild.Source(
                        BuildSpec=yaml.safe_dump(stages.get("Build", {}).get("BuildSpec")),
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
                                codepipeline.InputArtifacts(Name=build_input_artifact_name),
                            ],
                            ActionTypeId=codepipeline.ActionTypeId(
                                Category="Build",
                                Owner="AWS",
                                Version="1",
                                Provider="CodeBuild",
                            ),
                            OutputArtifacts=[
                                codepipeline.OutputArtifacts(Name=base_template.BUILD_OUTPUT_ARTIFACT)
                            ],
                            Configuration={
                                "ProjectName": t.Sub("${AWS::StackName}-BuildProject"),
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
                                        ]
                                    )
                                ),
                            },
                        )
                    ]
                )
            )

        pipeline_stages.append(
            self.build_test_stage(test_input_artifact_name, options)
        )

        if stages.get("Package", {}).get("BuildSpec"):
            # TODO - need to jinja render it
            package_build_spec = stages.get("Package", {}).get("BuildSpec")
        else:
            package_build_spec = yaml.safe_dump(
                {
                    "version": "0.2",
                    "phases": {
                        "install": {
                            "runtime-version": {
                                "python": "3.8"
                            }
                        },
                        "build": {
                            "commands": [
                                f"aws cloudformation package --region {region} --template $(pwd)/$CATEGORY.template.$TEMPLATE_FORMAT --s3-bucket sc-factory-artifacts-$ACCOUNT_ID-{region} --s3-prefix $STACK_NAME --output-template-file $CATEGORY.template-{region}.$TEMPLATE_FORMAT"
                                for region in all_regions
                            ],
                        }
                    }
                }
            )

        package_project_name = t.Sub("${AWS::StackName}-PackageProject")
        deploy_project_name = t.Sub("${AWS::StackName}-DeployProject")
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
                    Image=stages.get("Build", {}).get("BuildSpecImage", constants.ENVIRONMENT_IMAGE_DEFAULT),
                    Type=constants.ENVIRONMENT_TYPE_DEFAULT,
                    EnvironmentVariables=[
                        codebuild.EnvironmentVariable(
                            Name="TEMPLATE_FORMAT",
                            Type="PLAINTEXT",
                            Value="yaml",
                        ),
                        codebuild.EnvironmentVariable(
                            Name="CATEGORY",
                            Type="PLAINTEXT",
                            Value="stack",
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
                    ],
                ),
                Source=codebuild.Source(
                    BuildSpec=package_build_spec,
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
                            codepipeline.InputArtifacts(Name=package_input_artifact_name),
                        ],
                        ActionTypeId=codepipeline.ActionTypeId(
                            Category="Build",
                            Owner="AWS",
                            Version="1",
                            Provider="CodeBuild",
                        ),
                        OutputArtifacts=[
                            codepipeline.OutputArtifacts(Name=base_template.PACKAGE_OUTPUT_ARTIFACT)
                        ],
                        Configuration={
                            "ProjectName": package_project_name,
                            "PrimarySource": package_input_artifact_name,
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
                    )
                ]
            )
        )

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
                            Name="TEMPLATE_FORMAT",
                            Type="PLAINTEXT",
                            Value="yaml",
                        ),
                        codebuild.EnvironmentVariable(
                            Name="CATEGORY",
                            Type="PLAINTEXT",
                            Value="stack",
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
                                "install": {
                                    "runtime-version": {
                                        "python": "3.8"
                                    }
                                },
                                "build": {
                                    "commands": [
                                        f"aws s3 cp $CATEGORY.template.$TEMPLATE_FORMAT s3://sc-puppet-stacks-repository-$ACCOUNT_ID/{name}/{version}/$CATEGORY.template.$TEMPLATE_FORMAT"
                                    ],
                                }
                            }
                        }
                    ),
                    Type="CODEPIPELINE",
                ),
                Description=t.Sub("build project"),
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
                            codepipeline.InputArtifacts(Name=base_template.PACKAGE_OUTPUT_ARTIFACT),
                        ],
                        ActionTypeId=codepipeline.ActionTypeId(
                            Category="Build",
                            Owner="AWS",
                            Version="1",
                            Provider="CodeBuild",
                        ),
                        OutputArtifacts=[
                            codepipeline.OutputArtifacts(Name=base_template.DEPLOY_OUTPUT_ARTIFACT)
                        ],
                        Configuration={
                            "ProjectName": deploy_project_name,
                            "PrimarySource": base_template.DEPLOY_OUTPUT_ARTIFACT,
                        },
                    )
                ]
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
