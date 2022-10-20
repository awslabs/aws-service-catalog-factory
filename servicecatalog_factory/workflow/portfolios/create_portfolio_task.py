#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import json

import luigi

from servicecatalog_factory import aws
from servicecatalog_factory.workflow.tasks import FactoryTask, logger


class CreatePortfolioTask(FactoryTask):
    region = luigi.Parameter()
    portfolio_name = luigi.Parameter()
    description = luigi.Parameter(significant=False)
    provider_name = luigi.Parameter(significant=False)
    tags = luigi.ListParameter(default=[], significant=False)

    def params_for_results_display(self):
        return {
            "region": self.region,
            "portfolio_name": self.portfolio_name,
            "task_reference": self.task_reference,
        }

    def run(self):
        with self.regional_client("servicecatalog") as service_catalog:
            tags = []
            if self.should_pipelines_inherit_tags:
                tags += list(self.initialiser_stack_tags)
            for t in self.tags:
                tags.append(
                    {"Key": t.get("Key"), "Value": t.get("Value"),}
                )
            tags.append({"Key": "ServiceCatalogFactory:Actor", "Value": "Portfolio"})

            portfolio_detail = aws.get_or_create_portfolio(
                self.description,
                self.provider_name,
                self.portfolio_name,
                tags,
                service_catalog,
            )

        if portfolio_detail is None:
            raise Exception("portfolio_detail was not found or created")

        self.write_output(portfolio_detail)
