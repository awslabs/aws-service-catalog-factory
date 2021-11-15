#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import json

import luigi

from servicecatalog_factory import constants
from servicecatalog_factory import utils
from servicecatalog_factory.workflow.portfolios.create_portfolio_task import (
    CreatePortfolioTask,
)
from servicecatalog_factory.workflow.tasks import FactoryTask


class CreatePortfolioAssociationTask(FactoryTask):
    region = luigi.Parameter()
    portfolio_group_name = luigi.Parameter()
    display_name = luigi.Parameter()
    description = luigi.Parameter(significant=False)
    provider_name = luigi.Parameter(significant=False)
    tags = luigi.ListParameter(default=[], significant=False)

    associations = luigi.ListParameter(significant=False, default=[])
    factory_version = luigi.Parameter()

    def requires(self):
        return CreatePortfolioTask(
            self.region,
            self.portfolio_group_name,
            self.display_name,
            self.description,
            self.provider_name,
            self.tags,
        )

    def params_for_results_display(self):
        return {
            "region": self.region,
            "portfolio_group_name": self.portfolio_group_name,
            "display_name": self.display_name,
        }

    def output(self):
        output_file = f"output/CreatePortfolioAssociationTask/{self.region}-{self.portfolio_group_name}-{self.display_name}.json"
        return luigi.LocalTarget(output_file)

    def run(self):
        with self.regional_client("cloudformation") as cloudformation:
            portfolio_details = json.loads(self.input().open("r").read())
            template = utils.ENV.get_template(constants.ASSOCIATIONS)
            rendered = template.render(
                FACTORY_VERSION=self.factory_version,
                portfolio={
                    "DisplayName": portfolio_details.get("DisplayName"),
                    "Associations": self.associations,
                },
                portfolio_id=portfolio_details.get("Id"),
            )
            stack_name = "-".join(
                [self.portfolio_group_name, self.display_name, "associations"]
            )
            cloudformation.create_or_update(
                StackName=stack_name, TemplateBody=rendered,
            )
