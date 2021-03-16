import json
import troposphere as t
import yaml
import os
from troposphere import codebuild
from troposphere import awslambda
from troposphere import cloudformation
from troposphere import iam
from servicecatalog_factory import config

PREFIX = "sct-synth-output"

START_PROJECT_CODE = open(
    f"{os.path.dirname(__file__)}/code.py",
    "r",
).read()


def create_cdk_pipeline(name, version, product_name, product_version, p) -> t.Template:
    description = "todo"
    template = t.Template(Description=description)
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
    template.add_parameter(t.Parameter("CDKDeployToolkitStackName", Type="String"))
    template.add_parameter(
        t.Parameter(
            "CDKDeployExtraArgs",
            Type="String",
            Default="",
            Description="Extra args to pass to CDK deploy",
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
                    template.add_parameter(t.Parameter(parameter_name, **parameter_details))
                cdk_deploy_parameter_args.append(
                    f"--parameters {artifact_name}:{parameter_name}=${{{parameter_name}}}"
                )

            for output_name, output_details in artifact_template.get(
                "Outputs", {}
            ).items():
                if template.outputs.get(output_name) is None:
                    template.add_output(t.Output(output_name, **output_details))
    cdk_deploy_parameter_args = " ".join(cdk_deploy_parameter_args)

    build_spec = dict(
        version=0.2,
        phases=dict(
            install={
                "commands": [
                    "env",
                    "aws s3 cp s3://sc-factory-artifacts-$ACCOUNT_ID-$REGION/cdk/1.0.0/$NAME-$VERSION.zip .",
                    "ls -l",
                    "unzip *.zip",
                    "ls -l",
                ]
            },
            build={
                "commands": [
                    'echo "building"',
                    # "npm run cdk deploy -- --toolkit-stack-name $CDK_DEPLOY_TOOLKIT_STACK_NAME $CDK_DEPLOY_EXTRA_ARGS $CDK_DEPLOY_PARAMETER_ARGS",
                    'echo "{" > result.json'
                    'echo ""Status" : "SUCCESS"," >> result.json',
                    'echo ""Reason" : "Configuration Complete"," >> result.json',
                    'echo ""UniqueId" : "$CODEBUILD_BUILD_ID"," >> result.json',
                    'echo ""Data" : "hello world"," >> result.json',
                    'echo "}" >> result.json' "curl -T result.json $ON_COMPLETE_URL",
                ]
            },
        ),
        artifacts=dict(name="CDKDeploy", files=[f"{PREFIX}/*", f"{PREFIX}/**/*",],),
    )

    CDKDeployRoleArn = template.add_resource(
        iam.Role(
            "CDKDeployRoleArn",
            Path="/",
            ManagedPolicyArns=[
                t.Sub("arn:${AWS::Partition}:iam::aws:policy/AdministratorAccess")
            ],
            AssumeRolePolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Action": ["sts:AssumeRole"],
                        "Effect": "Allow",
                        "Principal": {"Service": ["codebuild.amazonaws.com"]},
                    }
                ],
            },
        )
    )

    project_name = f"CDK-deploy-{product_name}-{product_version}"

    project = template.add_resource(
        codebuild.Project(
            "CDKDeploy",
            Name=project_name,
            ServiceRole=t.Ref(CDKDeployRoleArn),
            Tags=t.Tags.from_dict(**{"ServiceCatalogPuppet:Actor": "Framework"}),
            Artifacts=codebuild.Artifacts(Type="NO_ARTIFACTS"),
            TimeoutInMinutes=60,
            Environment=codebuild.Environment(
                ComputeType=t.Ref("CDKDeployComputeType"),
                Image=t.Ref("CDKDeployImage"),
                Type="LINUX_CONTAINER",
                EnvironmentVariables=[
                    {
                        "Type": "PLAINTEXT",
                        "Name": "CDK_DEPLOY_EXTRA_ARGS",
                        "Value": "CHANGE_ME",
                    },
                    {
                        "Type": "PLAINTEXT",
                        "Name": "CDK_DEPLOY_TOOLKIT_STACK_NAME",
                        "Value": "CHANGE_ME",
                    },
                    {"Type": "PLAINTEXT", "Name": "UId", "Value": "CHANGE_ME",},
                    {
                        "Type": "PLAINTEXT",
                        "Name": "PUPPET_ACCOUNT_ID",
                        "Value": "CHANGE_ME",
                    },
                    {
                        "Type": "PLAINTEXT",
                        "Name": "CDK_DEPLOY_PARAMETER_ARGS",
                        "Value": "CHANGE_ME",
                    },
                    {
                        "Type": "PLAINTEXT",
                        "Name": "ON_COMPLETE_URL",
                        "Value": "CHANGE_ME",
                    },
                    {
                        "Type": "PLAINTEXT",
                        "Name": "NAME",
                        "Value": product_name,
                    },
                    {
                        "Type": "PLAINTEXT",
                        "Name": "VERSION",
                        "Value": product_version,
                    },
                ],
            ),
            Source=codebuild.Source(
                BuildSpec=t.Sub(yaml.safe_dump(build_spec)), Type="NO_SOURCE",
            ),
            Description=t.Sub("Run CDK deploy for given source code"),
        )
    )

    LambdaExecutionRole = template.add_resource(
        iam.Role(
            "LambdaExecutionRole",
            Path="/",
            ManagedPolicyArns=[
                t.Sub(
                    "arn:${AWS::Partition}:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
                )
            ],
            AssumeRolePolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Action": ["sts:AssumeRole"],
                        "Effect": "Allow",
                        "Principal": {"Service": ["lambda.amazonaws.com"]},
                    }
                ],
            },
            Policies=[
                iam.Policy(
                    PolicyName="allowtrigger",
                    PolicyDocument={
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": ["codebuild:*"],
                                "Resource": "*",
                            }
                        ],
                    },
                )
            ],
        )
    )

    fun = template.add_resource(
        awslambda.Function(
            "StartCDKDeploy",
            FunctionName="servicecatalog-tools--StartCDKDeploy",
            Code=awslambda.Code(ZipFile=START_PROJECT_CODE),
            Handler="index.handler",
            Role=t.GetAtt(LambdaExecutionRole, "Arn"),
            Runtime="python3.7",
            MemorySize=awslambda.MEMORY_VALUES[0],
            Timeout=30,
        )
    )

    wait_condition_handle = template.add_resource(
        cloudformation.WaitConditionHandle("WaitConditionHandle",)
    )

    class DeployDetailsCustomResource(cloudformation.AWSCustomObject):
        resource_type = "Custom::DeployDetails"
        props = dict()

    deploy = template.add_resource(
        DeployDetailsCustomResource(
            "DeployDetails",
            ServiceToken=t.GetAtt(fun, "Arn"),
            Handle=t.Ref(wait_condition_handle),
            Project=project_name,
            CDK_DEPLOY_EXTRA_ARGS=t.Ref("CDKDeployExtraArgs"),
            CDK_DEPLOY_TOOLKIT_STACK_NAME=t.Ref("CDKDeployToolkitStackName"),
            PUPPET_ACCOUNT_ID=t.Ref("PuppetAccountId"),
            CDK_DEPLOY_PARAMETER_ARGS=t.Sub(cdk_deploy_parameter_args),
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

    return template
