#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import time

import luigi


from servicecatalog_factory import constants, config
from servicecatalog_factory.workflow.tasks import FactoryTask


class CreateProductTask(FactoryTask):
    region = luigi.Parameter()
    name = luigi.Parameter()
    owner = luigi.Parameter(significant=False)
    description = luigi.Parameter(significant=False)
    distributor = luigi.Parameter(significant=False)
    support_description = luigi.Parameter(significant=False)
    support_email = luigi.Parameter(significant=False)
    support_url = luigi.Parameter(significant=False)
    tags = luigi.ListParameter(default=[], significant=False)

    get_bucket_task_ref = luigi.Parameter()

    def params_for_results_display(self):
        return {
            "region": self.region,
            "name": self.name,
            "task_reference": self.task_reference,
        }

    def run(self):
        with self.regional_client("servicecatalog") as service_catalog:
            (
                found,
                product_view_summary,
            ) = self.check_and_update_product_if_product_exists(service_catalog)

            if not found:
                self.info(f"Not found product: {self.name}, creating")

                tags = [{"Key": "ServiceCatalogFactory:Actor", "Value": "Product"}] + [
                    {"Key": t.get("Key"), "Value": t.get("Value"),} for t in self.tags
                ]

                create_product_args = {
                    "ProductType": "CLOUD_FORMATION_TEMPLATE",
                    "ProvisioningArtifactParameters": {
                        "Name": "-",
                        "Type": "CLOUD_FORMATION_TEMPLATE",
                        "Description": "Placeholder version, do not provision",
                        "Info": {
                            "LoadTemplateFromURL": "https://{}.s3.{}.{}/{}".format(
                                self.get_output_from_reference_dependency(
                                    self.get_bucket_task_ref
                                ).get("s3_bucket_url"),
                                constants.HOME_REGION,
                                config.get_aws_url_suffix(),
                                "empty.template.yaml",
                            )
                        },
                    },
                    "Name": self.name,
                    "Owner": self.owner,
                    "Description": self.description,
                    "Distributor": self.distributor,
                    "SupportDescription": self.support_description,
                    "SupportEmail": self.support_email,
                    "SupportUrl": self.support_url,
                    "Tags": tags,
                }

                product_view_summary = (
                    service_catalog.create_product(**create_product_args)
                    .get("ProductViewDetail")
                    .get("ProductViewSummary")
                )
                product_id = product_view_summary.get("ProductId")
                self.info(f"Created product {self.name}, waiting for completion")
                while True:
                    time.sleep(2)
                    search_products_as_admin_response = (
                        service_catalog.search_products_as_admin_single_page()
                    )
                    products_ids = [
                        product_view_detail.get("ProductViewSummary").get("ProductId")
                        for product_view_detail in search_products_as_admin_response.get(
                            "ProductViewDetails"
                        )
                    ]
                    self.info(f"Looking for {product_id} in {products_ids}")
                    if product_id in products_ids:
                        self.info(f"Found {product_id} ")
                        break

            if product_view_summary is None:
                raise Exception(f"did not find or create a product")

            self.write_output(product_view_summary)

    def check_and_update_product_if_product_exists(self, service_catalog):
        search_products_as_admin_response = service_catalog.search_products_as_admin_single_page(
            Filters={"FullTextSearch": [self.name]}
        )
        found = False
        product_view_summary = None
        for product_view_details in search_products_as_admin_response.get(
            "ProductViewDetails"
        ):
            product_view_summary = product_view_details.get("ProductViewSummary")
            if product_view_summary.get("Name") == self.name:
                found = True
                self.info(f"Found product: {self.name}: {product_view_summary}")
                things_to_change = dict()
                if product_view_summary.get("Owner") != self.owner:
                    things_to_change["Owner"] = self.owner
                if product_view_summary.get("ShortDescription") != self.description:
                    things_to_change["Description"] = self.description
                if product_view_summary.get("Distributor") != self.distributor:
                    things_to_change["Distributor"] = self.distributor
                if (
                    product_view_summary.get("SupportDescription")
                    != self.support_description
                ):
                    things_to_change["SupportDescription"] = self.support_description
                if product_view_summary.get("SupportEmail") != self.support_email:
                    things_to_change["SupportEmail"] = self.support_email
                if product_view_summary.get("SupportUrl") != self.support_url:
                    things_to_change["SupportUrl"] = self.support_url

                if len(things_to_change.keys()) > 0:
                    service_catalog.update_product(
                        Id=product_view_summary.get("ProductId"), **things_to_change
                    )
                break
        return found, product_view_summary
