#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import json

import troposphere as t
import yaml
import jinja2
from deepmerge import always_merger

from servicecatalog_factory import config
from servicecatalog_factory import constants
from troposphere import codepipeline
from troposphere import codebuild
from servicecatalog_factory.template_builder import base_template
from servicecatalog_factory.template_builder import shared_resources
from servicecatalog_factory.template_builder import builders_base


class CFNSplitTemplateBuilder(builders_base.BaseTemplateBuilder):
    category = "notset"

    def build_build_stage(
        self, tpl, pipeline_stages, path, options, stages, build_input_artifact_name
    ):
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
                                                value=self.category,
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
                        ComputeType=stages.get("Build", {}).get(
                            "BuildEnvironmentComputeType",
                            constants.ENVIRONMENT_COMPUTE_TYPE_DEFAULT,
                        ),
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
                                Name="CATEGORY", Type="PLAINTEXT", Value=self.category,
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
                                                value=self.category,
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
            )

    def build_test_stage(
        self, tpl, pipeline_stages, path, options, stages, test_input_artifact_name
    ):
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
                                dict(
                                    name="CATEGORY",
                                    value=self.category,
                                    type="PLAINTEXT",
                                ),
                                dict(name="SOURCE_PATH", value=path, type="PLAINTEXT",),
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
                                        value=self.category,
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
                                        value=self.category,
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
                    Name="CloudFormationRSpec",
                )
            )

        self.add_custom_tests(tpl, stages, actions, test_input_artifact_name)
        pipeline_stages.append(codepipeline.Stages(Name="Tests", Actions=actions))

    def build_package_stage(
        self,
        tpl,
        pipeline_stages,
        path,
        stages,
        package_input_artifact_name,
        all_regions,
        name,
        version,
    ):
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
                                            type="PLAINTEXT",
                                            value="yaml",
                                        ),
                                        dict(
                                            name="CATEGORY",
                                            type="PLAINTEXT",
                                            value=self.category,
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
                                            name="SOURCE_PATH",
                                            type="PLAINTEXT",
                                            value=path,
                                        ),
                                        dict(
                                            name="NAME", type="PLAINTEXT", value=name,
                                        ),
                                        dict(
                                            name="VERSION",
                                            type="PLAINTEXT",
                                            value=version,
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
                                            name="ALL_REGIONS",
                                            type="PLAINTEXT",
                                            value=" ".join(all_regions),
                                        ),
                                    ]
                                )
                            ),
                        },
                    )
                ],
            )
        )

    def build(self, name, version, source, options, stages):
        factory_version = constants.VERSION
        template_description = f'{{"version": "{factory_version}", "framework": "servicecatalog-factory", "role": "product-pipeline", "type": "cloudformation", "category": "{self.category}"}}'
        tpl = t.Template(Description=template_description)

        pipeline_stages = []
        self.build_source_stage(tpl, pipeline_stages, source)

        path = source.get("Path", ".")

        all_regions = config.get_regions()

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

        self.build_build_stage(
            tpl, pipeline_stages, path, options, stages, build_input_artifact_name
        )
        self.build_test_stage(
            tpl, pipeline_stages, path, options, stages, test_input_artifact_name,
        )
        self.build_package_stage(
            tpl,
            pipeline_stages,
            path,
            stages,
            package_input_artifact_name,
            all_regions,
            name,
            version,
        )
        self.build_deploy_stage(
            tpl, pipeline_stages, path, deploy_input_artifact_name, name, version,
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


class StackTemplateBuilder(CFNSplitTemplateBuilder):
    category = "stack"

    def build_deploy_stage(
        self, tpl, pipeline_stages, path, deploy_input_artifact_name, name, version,
    ):
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
                            Name="CATEGORY", Type="PLAINTEXT", Value=self.category,
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
                                            value=self.category,
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
        )


class ProductTemplateBuilder(CFNSplitTemplateBuilder):
    category = "product"

    def build_deploy_stage(
        self, tpl, pipeline_stages, path, deploy_input_artifact_name, name, version,
    ):
        pipeline_stages.append(
            codepipeline.Stages(
                Name="Deploy",
                Actions=[
                    codepipeline.Actions(
                        Name="Deploy",
                        RunOrder=1,
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
                        Configuration={
                            "ProjectName": shared_resources.DEPLOY_VIA_CODEBUILD_PROJECT_NAME,
                            "EnvironmentVariables": t.Sub(
                                json.dumps(
                                    [
                                        dict(
                                            name="TEMPLATE_FORMAT",
                                            value="yaml",
                                            type="PLAINTEXT",
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
                                            name="SOURCE_PATH",
                                            value=path,
                                            type="PLAINTEXT",
                                        ),
                                        dict(
                                            name="NAME", value=name, type="PLAINTEXT",
                                        ),
                                        dict(
                                            name="VERSION",
                                            value=version,
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
