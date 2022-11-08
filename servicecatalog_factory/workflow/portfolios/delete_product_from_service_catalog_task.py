#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import luigi

from servicecatalog_factory import constants
from servicecatalog_factory.workflow.tasks import FactoryTask, logger


class DeleteProductFromServiceCatalogTask(FactoryTask):
    region = luigi.Parameter()
    name = luigi.Parameter()

    def params_for_results_display(self):
        return {
            "region": self.region,
            "name": self.name,
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
                self.delete_from_service_catalog(product_id, service_catalog)

                self.info(f"Finished Deleting {self.name}")
        self.write_output({"found_product": found_product})

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
