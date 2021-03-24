import click
from betterboto import client as betterboto_client
import time


def create_or_update_provisioning_artifact(
    region, product_id, version_name, template_url, description
):
    with betterboto_client.ClientContextManager(
        "servicecatalog", region_name=region
    ) as servicecatalog:
        click.echo(f"Creating: {version_name} in: {region} for: {product_id}")
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

        click.echo(f"Created: {new_provisioning_artifact_id} in: {region} for: {product_id} {version_name}")

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
                click.echo(f"Deleting version: {existing_provisioning_artifact_id} of: {version_name}")
                servicecatalog.delete_provisioning_artifact(
                    ProductId=product_id,
                    ProvisioningArtifactId=existing_provisioning_artifact_id,
                )
