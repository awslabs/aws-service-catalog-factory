#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import json

import luigi

from servicecatalog_factory import aws
from servicecatalog_factory.workflow.tasks import FactoryTask, logger


class CreatePortfolioTask(FactoryTask):
    region = luigi.Parameter()
    portfolio_group_name = luigi.Parameter()
    display_name = luigi.Parameter()
    description = luigi.Parameter(significant=False)
    provider_name = luigi.Parameter(significant=False)
    tags = luigi.ListParameter(default=[], significant=False)

    def params_for_results_display(self):
        return {
            "region": self.region,
            "portfolio_group_name": self.portfolio_group_name,
            "display_name": self.display_name,
        }

    def output(self):
        output_file = f"output/CreatePortfolioTask/{self.region}-{self.portfolio_group_name}-{self.display_name}.json"
        return luigi.LocalTarget(output_file)

    def run(self):
        logger_prefix = f"{self.region}-{self.portfolio_group_name}-{self.display_name}"
        with self.regional_client("servicecatalog") as service_catalog:
            generated_portfolio_name = (
                f"{self.portfolio_group_name}-{self.display_name}"
            )
            tags = []
            for t in self.tags:
                tags.append(
                    {"Key": t.get("Key"), "Value": t.get("Value"),}
                )
            tags.append({"Key": "ServiceCatalogFactory:Actor", "Value": "Portfolio"})

            portfolio_detail = aws.get_or_create_portfolio(
                self.description,
                self.provider_name,
                generated_portfolio_name,
                tags,
                service_catalog,
            )

        if portfolio_detail is None:
            raise Exception("portfolio_detail was not found or created")

        with self.output().open("w") as f:
            logger.info(f"{logger_prefix}: about to write! {portfolio_detail}")
            f.write(json.dumps(portfolio_detail, indent=4, default=str,))
