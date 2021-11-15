#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import json
import troposphere as t
import yaml
from troposphere import cloudformation
from troposphere import codebuild
from servicecatalog_factory import constants

PREFIX = "sct-synth-output"


def create_cdk_pipeline(
    name, version, product_name, product_version, template_config, p
) -> t.Template:
    description = f"""Builds a cdk pipeline
{{"version": "{constants.VERSION}", "framework": "servicecatalog-factory", "role": "product-pipeline", "type": "{name}", "version": "{version}"}}"""
    configuration = template_config.get("Configuration")
    template = t.Template(Description=description)

    template.add_parameter(t.Parameter("PuppetAccountId", Type="String"))
    template.add_parameter(
        t.Parameter(
            "CDKSupportCDKDeployRequireApproval", Type="String", Default="never"
        )
    )
    template.add_parameter(
        t.Parameter(
            "CDKSupportCDKComputeType", Type="String", Default="BUILD_GENERAL1_SMALL"
        )
    )
    template.add_parameter(
        t.Parameter(
            "CDKSupportCDKDeployImage",
            Type="String",
            Default="aws/codebuild/standard:4.0",
        )
    )
    template.add_parameter(
        t.Parameter(
            "CDKSupportCDKToolkitStackName", Type="String", Default="CDKToolKit"
        )
    )
    template.add_parameter(
        t.Parameter(
            "CDKSupportCDKDeployExtraArgs",
            Type="String",
            Default="",
            Description="Extra args to pass to CDK deploy",
        )
    )
    template.add_parameter(
        t.Parameter("CDKSupportStartCDKDeployFunctionArn", Type="String",)
    )
    template.add_parameter(
        t.Parameter(
            "CDKSupportGetOutputsForGivenCodebuildIdFunctionArn", Type="String",
        )
    )
    template.add_parameter(
        t.Parameter(
            "CDKSupportIAMRolePaths",
            Type="String",
            Default="/servicecatalog-factory-cdk-support/",
        )
    )
    template.add_parameter(
        t.Parameter(
            "CDKSupportCDKDeployRoleName", Type="String", Default="CDKDeployRoleName"
        )
    )

    manifest = json.loads(open(f"{p}/{PREFIX}/manifest.json", "r").read())

    cdk_deploy_parameter_args = list()

    for artifact_name, artifact in manifest.get("artifacts", {}).items():
        if artifact.get("type") == "aws:cloudformation:stack":
            artifact_template_file_path = artifact.get("properties", {}).get(
                "templateFile"
            )
            assert (
                artifact_template_file_path
            ), f"Could not find template file in manifest.json for {artifact_name}"
            artifact_template = json.loads(
                open(f"{p}/{PREFIX}/{artifact_template_file_path}", "r").read()
            )
            for parameter_name, parameter_details in artifact_template.get(
                "Parameters", {}
            ).items():
                if template.parameters.get(parameter_name) is None:
                    template.add_parameter(
                        t.Parameter(parameter_name, **parameter_details)
                    )
                cdk_deploy_parameter_args.append(
                    f"--parameters {artifact_name}:{parameter_name}=${{{parameter_name}}}"
                )

            for output_name, output_details in artifact_template.get(
                "Outputs", {}
            ).items():
                if template.outputs.get(output_name) is None:
                    new_output = dict(**output_details)
                    new_output["Value"] = t.GetAtt("GetOutputsCode", output_name)
                    template.add_output(t.Output(output_name, **new_output))
    cdk_deploy_parameter_args = " ".join(cdk_deploy_parameter_args)

    class DeployDetailsCustomResource(cloudformation.AWSCustomObject):
        resource_type = "Custom::DeployDetails"
        props = dict()

    runtime_versions = dict(nodejs=constants.BUILDSPEC_RUNTIME_VERSIONS_NODEJS_DEFAULT,)
    if configuration.get("runtime-versions"):
        runtime_versions.update(configuration.get("runtime-versions"))

    extra_commands = list(configuration.get("install", {}).get("commands", []))

    template.add_resource(
        codebuild.Project(
            "CDKDeploy",
            Name=t.Sub("${AWS::StackName}-deploy"),
            Description="Run CDK deploy for given source code",
            ServiceRole=t.Sub(
                "arn:aws:iam::${AWS::AccountId}:role${CDKSupportIAMRolePaths}${CDKSupportCDKDeployRoleName}"
            ),
            Artifacts=codebuild.Artifacts(Type="NO_ARTIFACTS",),
            Environment=codebuild.Environment(
                ComputeType=t.Ref("CDKSupportCDKComputeType"),
                EnvironmentVariables=[
                    codebuild.EnvironmentVariable(
                        Name="CDK_DEPLOY_REQUIRE_APPROVAL",
                        Type="PLAINTEXT",
                        Value="CHANGE_ME",
                    ),
                    codebuild.EnvironmentVariable(
                        Name="CDK_DEPLOY_EXTRA_ARGS",
                        Type="PLAINTEXT",
                        Value="CHANGE_ME",
                    ),
                    codebuild.EnvironmentVariable(
                        Name="CDK_TOOLKIT_STACK_NAME",
                        Type="PLAINTEXT",
                        Value="CHANGE_ME",
                    ),
                    codebuild.EnvironmentVariable(
                        Name="UId", Type="PLAINTEXT", Value="CHANGE_ME"
                    ),
                    codebuild.EnvironmentVariable(
                        Name="PUPPET_ACCOUNT_ID", Type="PLAINTEXT", Value="CHANGE_ME"
                    ),
                    codebuild.EnvironmentVariable(
                        Name="REGION", Type="PLAINTEXT", Value=t.Ref("AWS::Region")
                    ),
                    codebuild.EnvironmentVariable(
                        Name="CDK_DEPLOY_PARAMETER_ARGS",
                        Type="PLAINTEXT",
                        Value="CHANGE_ME",
                    ),
                    codebuild.EnvironmentVariable(
                        Name="ON_COMPLETE_URL", Type="PLAINTEXT", Value="CHANGE_ME"
                    ),
                    codebuild.EnvironmentVariable(
                        Name="NAME", Type="PLAINTEXT", Value="CHANGE_ME"
                    ),
                    codebuild.EnvironmentVariable(
                        Name="VERSION", Type="PLAINTEXT", Value="CHANGE_ME"
                    ),
                ],
                Image=t.Ref("CDKSupportCDKDeployImage"),
                Type="LINUX_CONTAINER",
            ),
            Source=codebuild.Source(
                Type="NO_SOURCE",
                BuildSpec=t.Sub(
                    yaml.safe_dump(
                        dict(
                            version=0.2,
                            phases=dict(
                                install={
                                    "runtime-versions": runtime_versions,
                                    "commands": [
                                        "aws s3 cp s3://sc-factory-artifacts-$PUPPET_ACCOUNT_ID-$REGION/CDK/1.0.0/$NAME/$VERSION/$NAME-$VERSION.zip $NAME-$VERSION.zip",
                                        "unzip $NAME-$VERSION.zip",
                                        "npm install",
                                    ]
                                    + extra_commands,
                                },
                                build={
                                    "commands": [
                                        "npm run cdk deploy -- --toolkit-stack-name $CDK_TOOLKIT_STACK_NAME --require-approval $CDK_DEPLOY_REQUIRE_APPROVAL --outputs-file scf_outputs.json $CDK_DEPLOY_EXTRA_ARGS $CDK_DEPLOY_PARAMETER_ARGS '*'",
                                        "aws s3 cp scf_outputs.json s3://sc-cdk-artifacts-${AWS::AccountId}/CDK/1.0.0/$NAME/$VERSION/scf_outputs-$CODEBUILD_BUILD_ID.json",
                                    ]
                                },
                            ),
                            artifacts={"name": "CDKDeploy", "files": ["*", "**/*"],},
                        )
                    )
                ),
            ),
            TimeoutInMinutes=480,
        )
    )

    template.add_resource(
        codebuild.Project(
            "CDKDestroy",
            Name=t.Sub("${AWS::StackName}-destroy"),
            Description="Run CDK destroy for given source code",
            ServiceRole=t.Sub(
                "arn:aws:iam::${AWS::AccountId}:role${CDKSupportIAMRolePaths}${CDKSupportCDKDeployRoleName}"
            ),
            Artifacts=codebuild.Artifacts(Type="NO_ARTIFACTS",),
            Environment=codebuild.Environment(
                ComputeType=t.Ref("CDKSupportCDKComputeType"),
                EnvironmentVariables=[
                    codebuild.EnvironmentVariable(
                        Name="CDK_DEPLOY_REQUIRE_APPROVAL",
                        Type="PLAINTEXT",
                        Value="CHANGE_ME",
                    ),
                    codebuild.EnvironmentVariable(
                        Name="CDK_DEPLOY_EXTRA_ARGS",
                        Type="PLAINTEXT",
                        Value="CHANGE_ME",
                    ),
                    codebuild.EnvironmentVariable(
                        Name="CDK_TOOLKIT_STACK_NAME",
                        Type="PLAINTEXT",
                        Value="CHANGE_ME",
                    ),
                    codebuild.EnvironmentVariable(
                        Name="UId", Type="PLAINTEXT", Value="CHANGE_ME"
                    ),
                    codebuild.EnvironmentVariable(
                        Name="PUPPET_ACCOUNT_ID", Type="PLAINTEXT", Value="CHANGE_ME"
                    ),
                    codebuild.EnvironmentVariable(
                        Name="REGION", Type="PLAINTEXT", Value=t.Ref("AWS::Region")
                    ),
                    codebuild.EnvironmentVariable(
                        Name="CDK_DEPLOY_PARAMETER_ARGS",
                        Type="PLAINTEXT",
                        Value="CHANGE_ME",
                    ),
                    codebuild.EnvironmentVariable(
                        Name="ON_COMPLETE_URL", Type="PLAINTEXT", Value="CHANGE_ME"
                    ),
                    codebuild.EnvironmentVariable(
                        Name="NAME", Type="PLAINTEXT", Value="CHANGE_ME"
                    ),
                    codebuild.EnvironmentVariable(
                        Name="VERSION", Type="PLAINTEXT", Value="CHANGE_ME"
                    ),
                ],
                Image=t.Ref("CDKSupportCDKDeployImage"),
                Type="LINUX_CONTAINER",
            ),
            Source=codebuild.Source(
                Type="NO_SOURCE",
                BuildSpec=t.Sub(
                    yaml.safe_dump(
                        dict(
                            version=0.2,
                            phases=dict(
                                install={
                                    "runtime-versions": runtime_versions,
                                    "commands": [
                                        "aws s3 cp s3://sc-factory-artifacts-$PUPPET_ACCOUNT_ID-$REGION/CDK/1.0.0/$NAME/$VERSION/$NAME-$VERSION.zip $NAME-$VERSION.zip",
                                        "unzip $NAME-$VERSION.zip",
                                        "npm install",
                                    ]
                                    + extra_commands,
                                },
                                build={
                                    "commands": [
                                        "npm run cdk destroy -- --toolkit-stack-name $CDK_TOOLKIT_STACK_NAME --force --ignore-errors '*'"
                                    ]
                                },
                            ),
                            artifacts={"name": "CDKDeploy", "files": ["*", "**/*"],},
                        )
                    )
                ),
            ),
            TimeoutInMinutes=480,
        )
    )

    template.add_resource(
        DeployDetailsCustomResource(
            "StartCDKDeploy",
            DependsOn=["CDKDeploy", "CDKDestroy"],
            ServiceToken=t.Ref("CDKSupportStartCDKDeployFunctionArn"),
            CreateUpdateProject=t.Ref("CDKDeploy"),
            DeleteProject=t.Ref("CDKDestroy"),
            CDK_DEPLOY_EXTRA_ARGS=t.Ref("CDKSupportCDKDeployExtraArgs"),
            CDK_TOOLKIT_STACK_NAME=t.Ref("CDKSupportCDKToolkitStackName"),
            PUPPET_ACCOUNT_ID=t.Ref("PuppetAccountId"),
            CDK_DEPLOY_PARAMETER_ARGS=t.Sub(cdk_deploy_parameter_args),
            CDK_DEPLOY_REQUIRE_APPROVAL=t.Ref("CDKSupportCDKDeployRequireApproval"),
            NAME=product_name,
            VERSION=product_version,
        )
    )

    template.add_resource(
        DeployDetailsCustomResource(
            "GetOutputsCode",
            DependsOn=["StartCDKDeploy",],
            ServiceToken=t.Ref("CDKSupportGetOutputsForGivenCodebuildIdFunctionArn"),
            CodeBuildBuildId=t.GetAtt("StartCDKDeploy", "BuildId"),
            BucketName=t.Sub("sc-cdk-artifacts-${AWS::AccountId}"),
            ObjectKeyPrefix=t.Sub(f"CDK/1.0.0/{product_name}/{product_version}"),
        )
    )

    return template
