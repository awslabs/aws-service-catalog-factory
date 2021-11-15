#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import json
import time

import luigi

from servicecatalog_factory import constants
from servicecatalog_factory.workflow.portfolios.get_bucket_task import GetBucketTask
from servicecatalog_factory.workflow.tasks import FactoryTask, logger


class CreateProductTask(FactoryTask):
    uid = luigi.Parameter()
    region = luigi.Parameter()
    name = luigi.Parameter()
    owner = luigi.Parameter(significant=False)
    description = luigi.Parameter(significant=False)
    distributor = luigi.Parameter(significant=False)
    support_description = luigi.Parameter(significant=False)
    support_email = luigi.Parameter(significant=False)
    support_url = luigi.Parameter(significant=False)
    tags = luigi.ListParameter(default=[], significant=False)

    def params_for_results_display(self):
        return {
            "region": self.region,
            "uid": self.uid,
            "name": self.name,
        }

    def requires(self):
        return {"s3_bucket_url": GetBucketTask()}

    def output(self):
        return luigi.LocalTarget(
            f"output/CreateProductTask/{self.region}-{self.name}.json"
        )

    def run(self):
        logger_prefix = f"{self.region}-{self.name}"
        with self.regional_client("servicecatalog") as service_catalog:
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
                    logger.info(f"Found product: {self.name}: {product_view_summary}")
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
                        things_to_change[
                            "SupportDescription"
                        ] = self.support_description
                    if product_view_summary.get("SupportEmail") != self.support_email:
                        things_to_change["SupportEmail"] = self.support_email
                    if product_view_summary.get("SupportUrl") != self.support_url:
                        things_to_change["SupportUrl"] = self.support_url

                    if len(things_to_change.keys()) > 0:
                        service_catalog.update_product(
                            Id=product_view_summary.get("ProductId"), **things_to_change
                        )
                    break

            if not found:
                logger.info(f"Not found product: {self.name}, creating")

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
                            "LoadTemplateFromURL": "https://{}.s3.{}.amazonaws.com/{}".format(
                                self.load_from_input("s3_bucket_url").get(
                                    "s3_bucket_url"
                                ),
                                constants.HOME_REGION,
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
                logger.info(f"Created product {self.name}, waiting for completion")
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
                    logger.info(f"Looking for {product_id} in {products_ids}")
                    if product_id in products_ids:
                        logger.info(f"Found {product_id} ")
                        break

            if product_view_summary is None:
                raise Exception(f"{logger_prefix}: did not find or create a product")

            product_view_summary["uid"] = self.uid
            with self.output().open("w") as f:
                logger.info(f"{logger_prefix}: about to write! {product_view_summary}")
                f.write(json.dumps(product_view_summary, indent=4, default=str,))
