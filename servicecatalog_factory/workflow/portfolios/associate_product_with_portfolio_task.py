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
    portfolio_args = luigi.DictParameter()
    product_args = luigi.DictParameter()

    def params_for_results_display(self):
        return {
            "region": self.region,
            "portfolio": f"{self.portfolio_args.get('portfolio_group_name')}-{self.portfolio_args.get('display_name')}",
            "product": self.product_args.get("name"),
        }

    def output(self):
        return luigi.LocalTarget(
            f"output/AssociateProductWithPortfolioTask/"
            f"{self.region}"
            f"{self.product_args.get('name')}"
            f"_{self.portfolio_args.get('portfolio_group_name')}"
            f"_{self.portfolio_args.get('display_name')}.json"
        )

    def requires(self):
        return {
            "create_portfolio_task": CreatePortfolioTask(**self.portfolio_args),
            "create_product_task": CreateProductTask(**self.product_args),
        }

    def run(self):
        logger_prefix = f"{self.region}-{self.portfolio_args.get('portfolio_group_name')}-{self.portfolio_args.get('display_name')}"
        portfolio = json.loads(
            self.input().get("create_portfolio_task").open("r").read()
        )
        portfolio_id = portfolio.get("Id")
        product = json.loads(self.input().get("create_product_task").open("r").read())
        product_id = product.get("ProductId")
        with self.regional_client("servicecatalog") as service_catalog:
            logger.info(f"{logger_prefix}: Searching for existing association")

            aws.ensure_portfolio_association_for_product(
                portfolio_id, product_id, service_catalog
            )

            with self.output().open("w") as f:
                logger.info(f"{logger_prefix}: about to write!")
                f.write("{}")
