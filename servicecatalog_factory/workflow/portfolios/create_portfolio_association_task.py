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
    create_portfolio_task_ref = luigi.Parameter()
    portfolio_name = luigi.Parameter()
    associations = luigi.ListParameter()
    tags = luigi.ListParameter()

    factory_version = luigi.Parameter()

    def params_for_results_display(self):
        return {
            "region": self.region,
            "portfolio_name": self.portfolio_name,
        }

    def run(self):
        with self.regional_client("cloudformation") as cloudformation:
            create_portfolio_task_output = self.get_output_from_reference_dependency(
                self.create_portfolio_task_ref
            )
            template = utils.ENV.get_template(constants.ASSOCIATIONS)
            rendered = template.render(
                FACTORY_VERSION=self.factory_version,
                portfolio={
                    "DisplayName": self.portfolio_name,
                    "Associations": self.associations,
                },
                portfolio_id=create_portfolio_task_output.get("Id"),
            )
            stack_name = "-".join([self.portfolio_name, "associations"])
            tags = [dict(Key="ServiceCatalogFactory:Actor", Value="Generated",)]
            if self.should_pipelines_inherit_tags:
                tags += list(self.initialiser_stack_tags)

            cloudformation.create_or_update(
                StackName=stack_name, TemplateBody=rendered, Tags=tags,
            )
