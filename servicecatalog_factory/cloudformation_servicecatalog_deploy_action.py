#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import io
import json
import os
import zipfile

import click
from betterboto import client as betterboto_client
import time


def deploy(pipeline_name, pipeline_region, codepipeline_id, region):
    action_configuration = set_template_url_for_codepipeline_id(
        pipeline_name, codepipeline_id, region
    )
    create_or_update_provisioning_artifact(
        region, pipeline_region, action_configuration
    )


def get_package_action_from(pipeline_name, codepipeline_id):
    with betterboto_client.ClientContextManager("codepipeline") as codepipeline:
        paginator = codepipeline.get_paginator("list_action_executions")
        pages = paginator.paginate(
            pipelineName=pipeline_name, filter={"pipelineExecutionId": codepipeline_id},
        )
        for page in pages:
            for action_execution_detail in page.get("actionExecutionDetails", []):
                if (
                    action_execution_detail.get("stageName")
                    == action_execution_detail.get("actionName")
                    == "Package"
                ):
                    return action_execution_detail
        raise Exception(f"Could not find Package action for {codepipeline_id}")


def set_template_url_for_codepipeline_id(pipeline_name, codepipeline_id, region):
    action = get_package_action_from(pipeline_name, codepipeline_id)
    environment_variables = json.loads(
        action["input"]["resolvedConfiguration"]["EnvironmentVariables"]
    )
    action_configuration = dict()
    for environment_variable in environment_variables:
        action_configuration[
            environment_variable.get("name")
        ] = environment_variable.get("value")

    #
    #
    # THIS NEEDS TO BE PASSED IN OR MADE THE SAME!!!  current error is that the template is not in the zip file
    #
    #
    return_key = "{PROVISIONER}/{region}/{NAME}/{VERSION}/{CODEPIPELINE_ID}/product.template.{TEMPLATE_FORMAT}".format(
        region=region, **action_configuration
    )

    print(return_key)

    output_artifacts = action.get("output").get("outputArtifacts")
    assert len(output_artifacts) == 1
    output_artifacts = output_artifacts[0]
    bucket = output_artifacts.get("s3location").get("bucket")
    key = output_artifacts.get("s3location").get("key")

    template_format = action_configuration.get("TEMPLATE_FORMAT")

    print(f"bucket is {bucket}")
    print(f"key is {key}")

    with betterboto_client.ClientContextManager("s3") as s3:
        template = (
            zipfile.ZipFile(
                io.BytesIO(s3.get_object(Bucket=bucket, Key=key).get("Body").read())
            )
            .open(f"product.template-{region}.{template_format}", "r")
            .read()
        )
        s3.put_object(
            Bucket=bucket, Key=return_key, Body=template,
        )
    action_configuration["BUCKET"] = bucket
    action_configuration["TEMPLATE_URL"] = return_key
    return action_configuration


def create_or_update_provisioning_artifact(
    region, pipeline_region, action_configuration
):
    version_name = action_configuration.get("VERSION")
    description = action_configuration.get("DESCRIPTION")
    product = action_configuration.get("NAME")
    provisioner = action_configuration.get("PROVISIONER")

    bucket = f"sc-factory-artifacts-{os.environ.get('ACCOUNT_ID')}-{os.environ.get('REGION')}"
    key = f"{provisioner}/{product}/product_ids.json"
    with betterboto_client.ClientContextManager("s3") as s3:
        body = s3.get_object(Bucket=bucket, Key=key,).get("Body").read()
        product_ids_by_region = json.loads(body)
        product_id = product_ids_by_region[region]

    bucket = action_configuration.get("BUCKET")
    template_url = f"https://{bucket}.s3.{pipeline_region}.amazonaws.com/{action_configuration.get('TEMPLATE_URL')}"

    with betterboto_client.ClientContextManager(
        "servicecatalog", region_name=region
    ) as servicecatalog:
        click.echo(
            f"Creating: {version_name} in: {region} for {product}: using: {template_url}"
        )

        response = servicecatalog.create_provisioning_artifact(
            ProductId=product_id,
            Parameters={
                "Name": version_name,
                "Description": description,
                "Info": {"LoadTemplateFromURL": template_url},
                "Type": "CLOUD_FORMATION_TEMPLATE",
                "DisableTemplateValidation": False,
            },
        )
        new_provisioning_artifact_id = response.get("ProvisioningArtifactDetail").get(
            "Id"
        )
        status = "CREATING"
        while status == "CREATING":
            time.sleep(3)
            status = servicecatalog.describe_provisioning_artifact(
                ProductId=product_id,
                ProvisioningArtifactId=new_provisioning_artifact_id,
            ).get("Status")

        if status == "FAILED":
            raise Exception("Creating the provisioning artifact failed")

        click.echo(
            f"Created: {new_provisioning_artifact_id} in: {region} for: {product_id} {version_name}"
        )

        click.echo(f"Checking for old versions of: {version_name} to delete")
        provisioning_artifact_details = servicecatalog.list_provisioning_artifacts_single_page(
            ProductId=product_id
        ).get(
            "ProvisioningArtifactDetails", []
        )
        for provisioning_artifact_detail in provisioning_artifact_details:
            if (
                provisioning_artifact_detail.get("Name") == version_name
                and provisioning_artifact_detail.get("Id")
                != new_provisioning_artifact_id
            ):
                existing_provisioning_artifact_id = provisioning_artifact_detail.get(
                    "Id"
                )
                click.echo(
                    f"Deleting version: {existing_provisioning_artifact_id} of: {version_name}"
                )
                servicecatalog.delete_provisioning_artifact(
                    ProductId=product_id,
                    ProvisioningArtifactId=existing_provisioning_artifact_id,
                )
