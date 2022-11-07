#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import luigi

from servicecatalog_factory.workflow.tasks import FactoryTask, logger


class EnsureProductVersionDetailsCorrectTask(FactoryTask):
    region = luigi.Parameter()
    version = luigi.DictParameter()
    create_product_task_ref = luigi.Parameter()

    def params_for_results_display(self):
        return {
            "region": self.region,
            "task_reference": self.task_reference,
        }

    def run(self):
        create_product_task_output = self.get_output_from_reference_dependency(
            self.create_product_task_ref
        )
        product_id = create_product_task_output.get("ProductId")
        product_name = create_product_task_output.get("Name")
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
                            f"Active status needs to change for: {product_name} {version_name}"
                        )
                        service_catalog.update_provisioning_artifact(
                            ProductId=product_id,
                            ProvisioningArtifactId=provisioning_artifact_detail.get(
                                "Id"
                            ),
                            Active=version_active,
                        )

        self.write_output_raw("{}")
