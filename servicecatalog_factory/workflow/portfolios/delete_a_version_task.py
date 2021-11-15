#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import luigi
from betterboto import client as betterboto_client

from servicecatalog_factory.workflow.portfolios.create_product_task import (
    CreateProductTask,
)
from servicecatalog_factory.workflow.tasks import FactoryTask


class DeleteAVersionTask(FactoryTask):
    product_args = luigi.DictParameter()
    version = luigi.Parameter()

    @property
    def resources(self):
        return {self.product_args.get("region"): 1}

    def params_for_results_display(self):
        return {
            "uid": self.product_args.get("uid"),
            "region": self.product_args.get("region"),
            "name": self.product_args.get("name"),
            "version": self.version,
        }

    def requires(self):
        return {"create_product": CreateProductTask(**self.product_args)}

    def run(self):
        product = self.load_from_input("create_product")
        product_id = product.get("ProductId")
        self.info(f"Starting delete of {product_id} {self.version}")
        region = self.product_args.get("region")
        found = False
        with betterboto_client.ClientContextManager(
            "servicecatalog", region_name=region,
        ) as servicecatalog:
            provisioning_artifact_details = servicecatalog.list_provisioning_artifacts_single_page(
                ProductId=product_id,
            ).get(
                "ProvisioningArtifactDetails", []
            )

            for provisioning_artifact_detail in provisioning_artifact_details:
                if provisioning_artifact_detail.get("Name") == self.version:
                    provisioning_artifact_id = provisioning_artifact_detail.get("Id")
                    self.info(f"Found version: {provisioning_artifact_id}, deleting it")
                    servicecatalog.delete_provisioning_artifact(
                        ProductId=product_id,
                        ProvisioningArtifactId=provisioning_artifact_id,
                    )
                    found = True
                    break

        if not found:
            self.info("Did not find product version to delete")

        product["found"] = found

        with betterboto_client.ClientContextManager(
            "cloudformation", region_name=region,
        ) as cloudformation:
            cloudformation.ensure_deleted(
                StackName=f"{product.get('uid')}-{self.version}"
            )

        self.write_output(product)
