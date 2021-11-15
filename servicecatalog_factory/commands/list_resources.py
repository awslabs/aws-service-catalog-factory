#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
from pathlib import Path

import cfn_tools
import click
import terminaltables
from jinja2 import Template

from servicecatalog_factory import constants


def list_resources():
    click.echo("# Framework resources")

    click.echo("## SSM Parameters used")
    click.echo(f"- {constants.CONFIG_PARAM_NAME}")

    for file in Path(__file__).parent.resolve().glob("*.template.yaml"):
        if "empty.template.yaml" == file.name:
            continue
        template_contents = Template(open(file, "r").read()).render()
        template = cfn_tools.load_yaml(template_contents)
        click.echo(f"## Resources for stack: {file.name.split('.')[0]}")
        table_data = [
            ["Logical Name", "Resource Type", "Name",],
        ]
        table = terminaltables.AsciiTable(table_data)
        for logical_name, resource in template.get("Resources").items():
            resource_type = resource.get("Type")

            name = "-"

            type_to_name = {
                "AWS::IAM::Role": "RoleName",
                "AWS::SSM::Parameter": "Name",
                "AWS::S3::Bucket": "BucketName",
                "AWS::CodePipeline::Pipeline": "Name",
                "AWS::CodeBuild::Project": "Name",
                "AWS::CodeCommit::Repository": "RepositoryName",
            }

            if type_to_name.get(resource_type) is not None:
                name = resource.get("Properties", {}).get(
                    type_to_name.get(resource_type), "Not Specified"
                )
                if not isinstance(name, str):
                    name = cfn_tools.dump_yaml(name)

            table_data.append([logical_name, resource_type, name])

        click.echo(table.table)
    click.echo(f"n.b. AWS::StackName evaluates to {constants.BOOTSTRAP_STACK_NAME}")
