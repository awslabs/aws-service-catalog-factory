#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import json

import luigi

from servicecatalog_factory.workflow.portfolios.create_product_task import (
    CreateProductTask,
)
from servicecatalog_factory.workflow.tasks import FactoryTask, logger


class EnsureProductVersionDetailsCorrect(FactoryTask):
    region = luigi.Parameter()
    version = luigi.DictParameter()
    product_args = luigi.DictParameter()

    def params_for_results_display(self):
        return {
            "region": self.region,
            "version": self.version.get("Name"),
            "product": self.product_args.get("name"),
        }

    def output(self):
        return luigi.LocalTarget(
            f"output/EnsureProductVersionDetailsCorrect/"
            f"{self.region}_{self.product_args.get('name')}_{self.version.get('Name')}.json"
        )

    def requires(self):
        return CreateProductTask(**self.product_args)

    def run(self):
        product = json.loads(self.input().open("r").read())
        product_id = product.get("ProductId")
        version_name = self.version.get("Name")
        version_active = self.version.get("Active", True)

        with self.regional_client("servicecatalog") as service_catalog:
            response = service_catalog.list_provisioning_artifacts(ProductId=product_id)
            logger.info("Checking through: {}".format(response))
            for provisioning_artifact_detail in response.get(
                "ProvisioningArtifactDetails", []
            ):
                if provisioning_artifact_detail.get("Name") == version_name:
                    logger.info(
                        f"Found matching: {version_name}: {provisioning_artifact_detail}"
                    )
                    if provisioning_artifact_detail.get("Active") != version_active:
                        logger.info(
                            f"Active status needs to change for: {product.get('Name')} {version_name}"
                        )
                        service_catalog.update_provisioning_artifact(
                            ProductId=product_id,
                            ProvisioningArtifactId=provisioning_artifact_detail.get(
                                "Id"
                            ),
                            Active=version_active,
                        )

        with self.output().open("w") as f:
            f.write("{}")
