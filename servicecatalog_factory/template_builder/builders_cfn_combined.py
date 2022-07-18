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


class CFNCombinedTemplateBuilder(builders_base.BaseTemplateBuilder):
    category = "notset"

    def build_build_stage(
            self, tpl, pipeline_stages, path, options, stages, build_input_artifact_name
    ):
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

    def build_test_stage(self, tpl, item, versions, test_input_artifact_name):
        options = item.get("Options", {})

        input_artifacts = list()
        output_artifacts = list()
        commands = list()
        secondary_artifacts = dict()
        count = 0
        commands.append("env")
        for version in versions:
            version_name = version.get('Name')
            base_directory = "$CODEBUILD_SRC_DIR" if count == 0 else f"$CODEBUILD_SRC_DIR_Source_{version_name}"
            input_artifacts.append(
                codepipeline.InputArtifacts(Name=f"{test_input_artifact_name}_{version_name}"),
            )
            output_artifacts.append(
                codepipeline.OutputArtifacts(Name=f"{base_template.VALIDATE_OUTPUT_ARTIFACT}_{version_name}"),
            )
            path = version.get("Source", {}).get("Path", ".")
            output = base_directory
            commands.append(
                f'echo "{path}" > {output}/path.txt'
            )
            secondary_artifacts[f"Validate_{version_name}"]= {
                "base-directory": base_directory,
                "files": "**/*"
            }
            count += 1

        commands.extend(
            [
                "cd $(servicecatalog-factory print-source-directory ${AWS::StackName}-pipeline $EXECUTION_ID Source)",
                "pwd",
                "cd $(cat path.txt)",
                "pwd",
                "export FactoryTemplateValidateBucket=$(aws cloudformation list-stack-resources --stack-name servicecatalog-factory --query 'StackResourceSummaries[?LogicalResourceId==`FactoryTemplateValidateBucket`].PhysicalResourceId' --output text)",
                "aws s3 cp $CATEGORY.template.$TEMPLATE_FORMAT s3://$FactoryTemplateValidateBucket/$CODEBUILD_BUILD_ID.$TEMPLATE_FORMAT",
                "aws cloudformation validate-template --template-url https://$FactoryTemplateValidateBucket.s3.$AWS_REGION.amazonaws.com/$CODEBUILD_BUILD_ID.$TEMPLATE_FORMAT",
            ]
        )

        common_args = dict(
            RunOrder=1,
            InputArtifacts=input_artifacts,
            RoleArn=t.Sub(
                "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/SourceRole"
            ),
            ActionTypeId=codepipeline.ActionTypeId(
                Category="Test", Owner="AWS", Version="1", Provider="CodeBuild",
            ),
            OutputArtifacts=output_artifacts,
        )
        validate_project_name = t.Sub("${AWS::StackName}-ValidateProject")
        tpl.add_resource(
            codebuild.Project(
                "ValidateProject",
                Name=validate_project_name,
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
                            Name="CATEGORY", Type="PLAINTEXT", Value="product",
                        ),
                        dict(Name="SOURCE_PATH", Value=".", Type="PLAINTEXT", ),
                    ],
                ),
                Source=codebuild.Source(
                    BuildSpec=t.Sub(
                        yaml.safe_dump(
                            dict(
                                version=0.2,
                                phases=dict(
                                    install={
                                        "runtime-versions": dict(python="3.7",),
                                        "commands": [
                                                        f"pip install {constants.VERSION}"
                                                        if "http" in constants.VERSION
                                                        else f"pip install aws-service-catalog-factory=={constants.VERSION}",
                                                    ]
                                    },
                                    build={
                                        "commands": commands
                                    }
                                ),
                                artifacts={
                                    "files":["**/*"],
                                    "secondary-artifacts": secondary_artifacts
                                },
                            ), width=9999
                        )
                    ),
                    Type="CODEPIPELINE",
                ),
                Description=t.Sub("Run validate"),
            )
        )

        actions = [
            codepipeline.Actions(
                **common_args,
                Configuration={
                    "ProjectName": validate_project_name,
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
                                    value=self.category,
                                    type="PLAINTEXT",
                                ),
                                dict(
                                    name="EXECUTION_ID",
                                    value="#{codepipeline.PipelineExecutionId}",
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
                    **common_args,
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
                    **common_args,
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
                                ]
                            )
                        ),
                    },
                    Name="CloudFormationRSpec",
                )
            )

        return codepipeline.Stages(Name="Tests", Actions=actions)

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
                            "commands": ["cd $SOURCE_PATH", ]
                                        + [
                                            f"aws cloudformation package --region {region} --template $(pwd)/$CATEGORY.template.$TEMPLATE_FORMAT --s3-bucket sc-factory-artifacts-$ACCOUNT_ID-{region} --s3-prefix $STACK_NAME --output-template-file $CATEGORY.template-{region}.$TEMPLATE_FORMAT"
                                            for region in all_regions
                                        ],
                        },
                    },
                    "artifacts": {"files": ["*", "**/*"], },
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
                                            name="DESCRIPTION",
                                            type="PLAINTEXT",
                                            value="TBA",
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
                                            name="CODEPIPELINE_ID",
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

    def build_source_stage(self, tpl, item, versions):
        actions = list()
        for version in versions:
            source = always_merger.merge(
                item.get("Source", {}), version.get("Source", {})
            )
            self.add_custom_provider_details_to_tpl(source, tpl)
            actions.append(
                self.get_source_action_for_source(source, source_name_suffix=f'_{version.get("Name")}')
            )
        return codepipeline.Stages(
            Name="Source",
            Actions=actions,
        )

    def build(self, name, item, versions, options, stages):
        factory_version = constants.VERSION
        template_description = f'{{"version": "{factory_version}", "framework": "servicecatalog-factory", "role": "product-pipeline", "type": "cloudformation", "category": "{self.category}"}}'
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

        pipeline_stages = [
            self.build_source_stage(tpl, item, versions),
            ## build_build_stage would go here
            self.build_test_stage(
                tpl, item, versions, test_input_artifact_name,
            ),
        ]

        # self.build_build_stage(
        #     tpl, pipeline_stages, path, options, stages, build_input_artifact_name
        # )

        # all_regions = config.get_regions()
        # self.build_package_stage(
        #     tpl,
        #     pipeline_stages,
        #     path,
        #     stages,
        #     package_input_artifact_name,
        #     all_regions,
        #     name,
        #     version,
        # )
        # self.build_deploy_stage(
        #     tpl,
        #     pipeline_stages,
        #     path,
        #     deploy_input_artifact_name,
        #     name,
        #     version,
        # )

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


class StackTemplateBuilder(CFNCombinedTemplateBuilder):
    category = "stack"

    def build_deploy_stage(
            self,
            tpl,
            pipeline_stages,
            path,
            deploy_input_artifact_name,
            name,
            version,
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
                            "artifacts": {"files": ["*", "**/*"], },
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


class ProductTemplateBuilder(CFNCombinedTemplateBuilder):
    category = "product"

    def build_deploy_stage(
            self,
            tpl,
            pipeline_stages,
            path,
            deploy_input_artifact_name,
            name,
            version,
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
                                            name="CODEPIPELINE_ID",
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
