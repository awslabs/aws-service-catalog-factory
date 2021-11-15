#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import luigi

from servicecatalog_factory import constants
from servicecatalog_factory.workflow.tasks import FactoryTask, logger


class DeleteProductTask(FactoryTask):
    uid = luigi.Parameter()
    region = luigi.Parameter()
    name = luigi.Parameter()
    pipeline_mode = luigi.Parameter()

    def params_for_results_display(self):
        return {
            "region": self.region,
            "uid": self.uid,
            "name": self.name,
            "pipeline_mode": self.pipeline_mode,
        }

    def run(self):
        with self.regional_client("servicecatalog") as service_catalog:
            self.info(f"Looking for product to delete: {self.name}")
            search_products_as_admin_response = service_catalog.search_products_as_admin_single_page(
                Filters={"FullTextSearch": [self.name]}
            )
            found_product = False
            for product_view_details in search_products_as_admin_response.get(
                "ProductViewDetails"
            ):
                product_view_summary = product_view_details.get("ProductViewSummary")
                if product_view_summary.get("Name") == self.name:
                    found_product = True
                    product_id = product_view_summary.get("ProductId")
                    logger.info(f"Found product: {self.name}: {product_view_summary}")
                    break

            if found_product:
                with self.regional_client("cloudformation") as cloudformation:
                    if self.pipeline_mode == constants.PIPELINE_MODE_SPILT:
                        self.delete_pipelines(
                            product_id, service_catalog, cloudformation
                        )
                    else:
                        self.info(f"Ensuring {self.name} is deleted")
                        cloudformation.ensure_deleted(StackName=self.name)

                self.delete_from_service_catalog(product_id, service_catalog)

                self.info(f"Finished Deleting {self.name}")
        self.write_output({"found_product": found_product})

    def delete_pipelines(self, product_id, service_catalog, cloudformation):
        list_versions_response = service_catalog.list_provisioning_artifacts_single_page(
            ProductId=product_id
        )
        version_names = [
            version["Name"]
            for version in list_versions_response.get("ProvisioningArtifactDetails", [])
        ]
        if len(version_names) > 0:
            self.info(
                f"Deleting Pipeline stacks for versions: {version_names} of {self.name}"
            )
            for version_name in version_names:
                self.info(f"Ensuring {self.uid}-{version_name} is deleted")
                cloudformation.ensure_deleted(StackName=f"{self.uid}-{version_name}")

    def delete_from_service_catalog(self, product_id, service_catalog):
        list_portfolios_response = service_catalog.list_portfolios_for_product_single_page(
            ProductId=product_id,
        )
        portfolio_ids = [
            portfolio_detail["Id"]
            for portfolio_detail in list_portfolios_response.get("PortfolioDetails", [])
        ]
        for portfolio_id in portfolio_ids:
            self.info(f"Disassociating {self.name} {product_id} from {portfolio_id}")
            service_catalog.disassociate_product_from_portfolio(
                ProductId=product_id, PortfolioId=portfolio_id
            )
        self.info(f"Deleting {self.name} {product_id} from Service Catalog")
        service_catalog.delete_product(Id=product_id,)
