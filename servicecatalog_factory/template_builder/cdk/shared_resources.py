import troposphere as t
from troposphere import codebuild
import yaml
from servicecatalog_factory import constants
from servicecatalog_factory import config
from servicecatalog_factory.template_builder.base_template import (
    BUILD_OUTPUT_ARTIFACT,
    PACKAGE_OUTPUT_ARTIFACT,
    DEPLOY_OUTPUT_ARTIFACT,
)

CDK_BUILD_PROJECT_NAME = "CDK-Build--1-0-0"
CDK_PACKAGE_PROJECT_NAME = "CDK-Package--1-0-0"
CDK_DEPLOY_PROJECT_NAME = "CDK-Deploy--1-0-0"

all_regions = config.get_regions()


def get_commands_for_deploy() -> list:
    commands = []
    for region in all_regions:
        url = f"https://sc-factory-artifacts-$ACCOUNT_ID-{region}.s3.{region}.amazonaws.com/cdk/1.0.0/$NAME/$VERSION/product.template-{region}.yaml"
        commands += [
            f"export R=$(echo {region} | sed 's/-/_/g')",
            "echo $R",
            'export PRODUCT_ID=$(eval "echo \$PRODUCT_ID_$R")',
            "echo $PRODUCT_ID",
            f"export PRODUCT_ID=$PRODUCT_ID_{region.replace('-','_')}",
            "echo $PRODUCT_ID",
        ]
        commands.append(
            f"echo aws servicecatalog create-provisioning-artifact --region {region} --product-id $PRODUCT_ID --parameters Name=$VERSION,Description=\"$DESCRIPTION\",Info={{LoadTemplateFromURL={url}}},Type=CLOUD_FORMATION_TEMPLATE"
        )
        commands.append(
            f"aws servicecatalog create-provisioning-artifact --region {region} --product-id $PRODUCT_ID --parameters Name=$VERSION,Description=\"$DESCRIPTION\",Info={{LoadTemplateFromURL={url}}},Type=CLOUD_FORMATION_TEMPLATE"
        )

    return commands


resources = [
    codebuild.Project(
        "CDKBuild100",
        Name=CDK_BUILD_PROJECT_NAME,
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
                {"Type": "PLAINTEXT", "Name": "NAME", "Value": "CHANGE_ME", },
                {"Type": "PLAINTEXT", "Name": "VERSION", "Value": "CHANGE_ME", },
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
                                    nodejs=constants.BUILDSPEC_RUNTIME_VERSIONS_NODEJS_DEFAULT,
                                ),
                                "commands": [
                                    f"pip install {constants.VERSION}"
                                    if "http" in constants.VERSION
                                    else f"pip install aws-service-catalog-puppet=={constants.VERSION}",
                                ],
                            },
                            pre_build={
                                "commands": [
                                    "npm install",
                                    "npm run cdk synth -- --output sct-synth-output",
                                ],
                            },
                            build={
                                "commands": [
                                    f"servicecatalog-factory generate-template CDK 1.0.0 $NAME $VERSION . > product.template.yaml",
                                ]
                            },
                        ),
                        artifacts={
                            "name": BUILD_OUTPUT_ARTIFACT,
                            "files": ["*", "**/*"],
                            "exclude-paths": ["node_modules/*"],
                        },
                    )
                )
            ),
            Type="CODEPIPELINE",
        ),
        Description=t.Sub("Create a build stage for template CDK 1.0.0"),
    ),
    codebuild.Project(
        "CDKPackage100",
        Name=CDK_PACKAGE_PROJECT_NAME,
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
                {
                    "Type": "PLAINTEXT",
                    "Name": "ACCOUNT_ID",
                    "Value": t.Sub("${AWS::AccountId}"),
                },
                {"Type": "PLAINTEXT", "Name": "NAME", "Value": "CHANGE_ME"},
                {"Type": "PLAINTEXT", "Name": "VERSION", "Value": "CHANGE_ME"},
            ],
        ),
        Source=codebuild.Source(
            BuildSpec=t.Sub(
                yaml.safe_dump(
                    dict(
                        version=0.2,
                        phases=dict(
                            build={
                                "commands": ['zip -r $NAME-$VERSION.zip . -x "node_modules/*"']
                                            + [
                                                f"aws cloudformation package --region {region} --template $(pwd)/product.template.yaml --s3-bucket sc-factory-artifacts-$ACCOUNT_ID-{region} --s3-prefix /cdk/1.0.0/$NAME/$VERSION --output-template-file product.template-{region}.yaml"
                                                for region in all_regions
                                            ]
                                            + [
                                                f"aws s3 cp --quiet product.template-{region}.yaml s3://sc-factory-artifacts-$ACCOUNT_ID-{region}/cdk/1.0.0/$NAME/$VERSION/product.template-{region}.yaml"
                                                for region in all_regions
                                            ]
                                            + [
                                                f"aws s3 cp --quiet $NAME-$VERSION.zip s3://sc-factory-artifacts-$ACCOUNT_ID-{region}/cdk/1.0.0/$NAME/$VERSION/$NAME-$VERSION.zip"
                                                for region in all_regions
                                            ]
                            },
                        ),
                        artifacts={
                            "name": PACKAGE_OUTPUT_ARTIFACT,
                            "files": ["*", "**/*"],
                            "exclude-paths": ["node_modules/*"],
                        },
                    )
                )
            ),
            Type="CODEPIPELINE",
        ),
        Description=t.Sub("Create a build stage for template CDK 1.0.0"),
    ),
    codebuild.Project(
        "CDKDeploy100",
        Name=CDK_DEPLOY_PROJECT_NAME,
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
                                     {
                                         "Type": "PLAINTEXT",
                                         "Name": "ACCOUNT_ID",
                                         "Value": t.Sub("${AWS::AccountId}"),
                                     },
                                     {"Type": "PLAINTEXT", "Name": "NAME", "Value": "CHANGE_ME"},
                                     {"Type": "PLAINTEXT", "Name": "VERSION", "Value": "CHANGE_ME"},
                                     {"Type": "PLAINTEXT", "Name": "DESCRIPTION", "Value": "CHANGE_ME"},
                                 ] + [
                                     dict(Name=f"PRODUCT_ID_{region.replace('-', '_')}", Value="CHANGE_ME",
                                          Type="PLAINTEXT") for region in all_regions
                                 ],
        ),
        Source=codebuild.Source(
            BuildSpec=t.Sub(
                yaml.safe_dump(
                    dict(
                        version=0.2,
                        phases=dict(
                            build={
                                "commands": get_commands_for_deploy()
                            },
                        ),
                        artifacts={
                            "name": DEPLOY_OUTPUT_ARTIFACT,
                            "files": ["*", "**/*"],
                            "exclude-paths": ["node_modules"],
                        },
                    )
                )
            ),
            Type="CODEPIPELINE",
        ),
        Description=t.Sub("Create a deploy stage for template CDK 1.0.0"),
    ),
]
