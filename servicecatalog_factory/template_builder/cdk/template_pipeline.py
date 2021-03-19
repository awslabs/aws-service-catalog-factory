# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import json
import troposphere as t
from troposphere import cloudformation
from servicecatalog_factory import constants

PREFIX = "sct-synth-output"


def create_cdk_pipeline(name, version, product_name, product_version, p) -> t.Template:
    description = f"""Bootstrap template used to bring up the main ServiceCatalog-Puppet AWS CodePipeline with dependencies
{{"version": "{constants.VERSION}", "framework": "servicecatalog-factory", "role": "product-pipeline", "type": "{name}", "version": "{version}"}}"""
    template = t.Template(Description=description)
    template.add_parameter(
        t.Parameter("CDKDeployRequireApproval", Type="String", Default="never")
    )
    template.add_parameter(
        t.Parameter(
            "CDKDeployComputeType", Type="String", Default="BUILD_GENERAL1_SMALL"
        )
    )
    template.add_parameter(
        t.Parameter(
            "CDKDeployImage", Type="String", Default="aws/codebuild/standard:4.0"
        )
    )
    template.add_parameter(t.Parameter("PuppetAccountId", Type="String"))
    template.add_parameter(
        t.Parameter("CDKToolkitStackName", Type="String", Default="CDKToolKit")
    )
    template.add_parameter(
        t.Parameter(
            "CDKDeployExtraArgs",
            Type="String",
            Default="",
            Description="Extra args to pass to CDK deploy",
        )
    )
    template.add_parameter(t.Parameter("StartCDKDeployFunctionArn", Type="String",))
    template.add_parameter(
        t.Parameter("GetOutputsForGivenCodebuildIdFunctionArn", Type="String",)
    )
    template.add_parameter(t.Parameter("CDKDeployProject", Type="String",))

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

    wait_condition_handle = template.add_resource(
        cloudformation.WaitConditionHandle("WaitConditionHandle",)
    )

    class DeployDetailsCustomResource(cloudformation.AWSCustomObject):
        resource_type = "Custom::DeployDetails"
        props = dict()

    template.add_resource(
        DeployDetailsCustomResource(
            "DeployDetails",
            ServiceToken=t.Ref("StartCDKDeployFunctionArn"),
            Handle=t.Ref(wait_condition_handle),
            Project=t.Ref("CDKDeployProject"),
            CDK_DEPLOY_EXTRA_ARGS=t.Ref("CDKDeployExtraArgs"),
            CDK_TOOLKIT_STACK_NAME=t.Ref("CDKToolkitStackName"),
            PUPPET_ACCOUNT_ID=t.Ref("PuppetAccountId"),
            CDK_DEPLOY_PARAMETER_ARGS=t.Sub(cdk_deploy_parameter_args),
            CDK_DEPLOY_REQUIRE_APPROVAL=t.Ref("CDKDeployRequireApproval"),
            NAME=product_name,
            VERSION=product_version,
        )
    )

    template.add_resource(
        cloudformation.WaitCondition(
            "WaiterCondition",
            DependsOn="DeployDetails",
            Handle=t.Ref(wait_condition_handle),
            Timeout=28800,
        )
    )

    template.add_resource(
        DeployDetailsCustomResource(
            "GetOutputsCode",
            DependsOn=["WaiterCondition", "WaitConditionHandle", "DeployDetails",],
            ServiceToken=t.Ref("GetOutputsForGivenCodebuildIdFunctionArn"),
            CodeBuildBuildId=t.GetAtt("DeployDetails", "BuildId"),
            BucketName=t.Sub("sc-factory-artifacts-${PuppetAccountId}-${AWS::Region}"),
            ObjectKeyPrefix=t.Sub(f"cdk/1.0.0/{product_name}/{product_version}"),
        )
    )

    return template
