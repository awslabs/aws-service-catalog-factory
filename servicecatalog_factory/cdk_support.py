import json
import troposphere as t
import yaml
from troposphere import codebuild
from troposphere import codepipeline
from troposphere import cloudformation
from servicecatalog_factory import config

PREFIX = "sct-synth-output"


def create_cdk_pipeline(p, uid):
    all_regions = config.get_regions()
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
    template.add_parameter(t.Parameter("CDKPipelineRoleArn", Type="String"))
    template.add_parameter(t.Parameter("CDKDeployRoleArn", Type="String"))
    template.add_parameter(
        t.Parameter(
            "CDKDeployExtraArgs",
            Type="String",
            Default="",
            Description="Extra args to pass to CDK deploy",
        )
    )

    manifest = json.loads(open(f"{p}/{PREFIX}/manifest.json", "r").read())


    cdk_deploy_parameter_env_vars = list()
    cdk_deploy_parameter_args = list()
    deploy_details_properties = dict()
    deploy_details_args = list()

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
                template.add_parameter(t.Parameter(parameter_name, **parameter_details))
                cdk_deploy_parameter_env_vars.append(
                    {
                        "Type": "PLAINTEXT",
                        "Name": parameter_name,
                        "Value": t.Ref(parameter_name),
                    }
                )
                cdk_deploy_parameter_args.append(
                    f"--parameters {artifact_name}:{parameter_name}=${{{parameter_name}}}"
                )
                deploy_details_args.append(t.Ref(parameter_name))

            for output_name, output_details in artifact_template.get(
                "Outputs", {}
            ).items():
                template.add_output(t.Output(output_name, **output_details))
                # deploy_details_properties[output_name] = (str, True)
    cdk_deploy_parameter_args = " ".join(cdk_deploy_parameter_args)

    build_spec = dict(
        version=0.2,
        phases=dict(
            install={
                "commands": [
                    'echo "installing"',
                    "npm install"
                ]
            },
            build={
                "commands": [
                    'echo "building"',
                    'npm run cdk deploy -- --toolkit-stack-name ${CDK_DEPLOY_TOOLKIT_STACK_NAME} ${CDK_DEPLOY_EXTRA_ARGS} ${CDK_DEPLOY_PARAMETER_ARGS}'
                ]
            },
        ),
        artifacts=dict(
            name="CDKDeploy",
            files=[
                f"{PREFIX}/*",
                f"{PREFIX}/**/*",
            ],
        ),
    )

    template.add_resource(
        codebuild.Project(
            "CDKDeploy",
            Name=t.Sub("${AWS::StackName}-cdk-deploy"),
            ServiceRole=t.Ref("CDKDeployRoleArn"),
            Tags=t.Tags.from_dict(
                **{"ServiceCatalogPuppet:Actor": "Framework"}
            ),
            Artifacts=codebuild.Artifacts(Type="CODEPIPELINE"),
            TimeoutInMinutes=60,
            Environment=codebuild.Environment(
                ComputeType=t.Ref("CDKDeployComputeType"),
                Image=t.Ref("CDKDeployImage"),
                Type="LINUX_CONTAINER",
                EnvironmentVariables=[
                    {
                        "Type": "PLAINTEXT",
                        "Name": "CDK_DEPLOY_TOOLKIT_STACK_NAME",
                        "Value": t.Ref("CDKDeployToolkitStackName"),
                    },
                    {
                        "Type": "PLAINTEXT",
                        "Name": "CDK_DEPLOY_EXTRA_ARGS",
                        "Value": t.Ref("CDKDeployExtraArgs"),
                    },
                    {
                        "Type": "PLAINTEXT",
                        "Name": "PUPPET_ACCOUNT_ID",
                        "Value": t.Ref("PuppetAccountId"),
                    },
                    {
                        "Type": "PLAINTEXT",
                        "Name": "CDK_DEPLOY_PARAMETER_ARGS",
                        "Value": cdk_deploy_parameter_args,
                    },
                ] + cdk_deploy_parameter_env_vars,
            ),
            Source=codebuild.Source(
                BuildSpec=yaml.safe_dump(build_spec),
                Type="CODEPIPELINE",
            ),
            Description=t.Sub("Run CDK deploy for ${AWS::StackName}"),
        )
    )

    source_stage = codepipeline.Stages(
        Name="Source",
        Actions=[
            codepipeline.Actions(
                RunOrder=1,
                ActionTypeId=codepipeline.ActionTypeId(
                    Category="Source", Owner="AWS", Version="1", Provider="S3",
                ),
                OutputArtifacts=[
                    codepipeline.OutputArtifacts(Name="Source")
                ],
                Configuration={
                    "S3Bucket": t.Sub("sc-factory-artifacts-${PuppetAccountId}-${AWS::Region}"),
                    "S3ObjectKey": f"{uid}/cdk-project.zip",
                    "PollForSourceChanges": False,
                },
                Name="Source",
            )
        ],
    )

    deploy_stage = codepipeline.Stages(
        Name="CDKDeploy",
        Actions=[
            codepipeline.Actions(
                InputArtifacts= [
                    codepipeline.InputArtifacts(Name="Source"),
                ],
                Name= "CDKDeploy",
                ActionTypeId= codepipeline.ActionTypeId(
                    Category="Build",
                    Owner="AWS",
                    Version="1",
                    Provider="CodeBuild",
                ),
                OutputArtifacts=[
                    codepipeline.OutputArtifacts(Name="CDKDeploy")
                ],
                Configuration= {
                    "ProjectName": t.Sub("${AWS::StackName}-cdk-deploy"),
                    "PrimarySource": "Source",
                },
                RunOrder= 1,
            )
        ]
    )

    template.add_resource(
        codepipeline.Pipeline(
            "CodePipeline",
            RoleArn=t.Ref("CDKPipelineRoleArn"),
            Stages=[source_stage, deploy_stage,],
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
            RestartExecutionOnUpdate=False,
        )
    )

    class DeployDetailsCustomResource(cloudformation.AWSCustomObject):
        resource_type = "Custom::DeployDetails"
        props = dict()

    template.add_resource(
        DeployDetailsCustomResource(
            "DeployDetails",
            NOnce=t.Join(",", deploy_details_args)
        )
    )

    print(template.to_yaml())
