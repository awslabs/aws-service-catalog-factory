#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import json

import luigi

from servicecatalog_factory import aws
from servicecatalog_factory.workflow.portfolios.create_portfolio_task import (
    CreatePortfolioTask,
)
from servicecatalog_factory.workflow.portfolios.create_product_task import (
    CreateProductTask,
)
from servicecatalog_factory.workflow.tasks import FactoryTask, logger


class AssociateProductWithPortfolioTask(FactoryTask):
    region = luigi.Parameter()
    create_product_task_ref = luigi.Parameter()
    create_portfolio_task_ref = luigi.Parameter()

    def params_for_results_display(self):
        return {
            "region": self.region,
            "create_product_task_ref": self.create_product_task_ref,
            "create_portfolio_task_ref": self.create_portfolio_task_ref,
        }

    def run(self):
        create_portfolio_task_output = self.get_output_from_reference_dependency(
            self.create_portfolio_task_ref
        )
        create_product_task_output = self.get_output_from_reference_dependency(
            self.create_product_task_ref
        )

        portfolio_id = create_portfolio_task_output.get("Id")
        product_id = create_product_task_output.get("ProductId")
        with self.regional_client("servicecatalog") as service_catalog:
            self.info(f"Searching for existing association")

            aws.ensure_portfolio_association_for_product(
                portfolio_id, product_id, service_catalog
            )

            self.write_output_raw("{}")
