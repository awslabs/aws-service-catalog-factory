#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
from servicecatalog_factory import config
from servicecatalog_factory import constants
from servicecatalog_factory.template_builder import pipeline_template_builder
from servicecatalog_factory.workflow import tasks
from servicecatalog_factory.workflow.portfolios import (
    associate_product_with_portfolio_task,
)
import luigi
from luigi.util import inherits


class CreateGenericCombinedPipelineTemplateTask(tasks.FactoryTask):
    pipeline_type = luigi.Parameter()
    category = luigi.Parameter()
    name = luigi.Parameter()
    item = luigi.DictParameter()
    versions = luigi.ListParameter()
    options = luigi.DictParameter()
    stages = luigi.DictParameter()
    tags = luigi.ListParameter()

    def params_for_results_display(self):
        versions = ",".join([version.get("Name") for version in self.versions])
        return {
            "category": self.category,
            "name": self.name,
            "versions": versions,
        }

    def output(self):
        versions = ",".join([version.get("Name") for version in self.versions])
        return luigi.LocalTarget(
            f"output/{self.__class__.__name__}/"
            f"{self.category}-{self.name}-{versions}.template.json"
        )

    def run(self):
        template = pipeline_template_builder.PipelineTemplate(
            self.category, constants.PIPELINE_MODE_COMBINED
        )
        builder = template.build(
            self.name, self.item, self.versions, self.options, self.stages
        )
        self.write_output_raw(builder.to_json())


@inherits(CreateGenericCombinedPipelineTemplateTask)
class CreateGenericCombinedPipelineTask(tasks.FactoryTask):
    pipeline_type = luigi.Parameter()
    category = luigi.Parameter()
    name = luigi.Parameter()
    item = luigi.DictParameter()
    versions = luigi.ListParameter()
    options = luigi.DictParameter()
    stages = luigi.DictParameter()
    tags = luigi.ListParameter()

    def params_for_results_display(self):
        versions = ",".join([version.get("Name") for version in self.versions])
        return {"category": self.category, "name": self.name, "versions": versions}

    def requires(self):
        required = dict(template=self.clone(CreateGenericCombinedPipelineTemplateTask))
        if self.category == "products":
            portfolio_tasks = list()
            all_regions = config.get_regions()
            for portfolio in self.item.get("Portfolios", []):
                if isinstance(portfolio, str):
                    continue

                for region in all_regions:
                    portfolio_args = dict(
                        region=region,
                        portfolio_group_name=portfolio.get("PortfolioGroupName", ""),
                        display_name=portfolio.get("DisplayName", ""),
                        description=portfolio.get("Description"),
                        provider_name=portfolio.get("ProviderName"),
                        portfolio_name=portfolio.get("PortfolioName", ""),
                        tags=portfolio.get("Tags", []),
                    )
                    product_args = dict(
                        region=region,
                        name=self.item.get("Name"),
                        owner=self.item.get("Owner"),
                        description=self.item.get("Description"),
                        distributor=self.item.get("Distributor"),
                        support_description=self.item.get("SupportDescription"),
                        support_email=self.item.get("SupportEmail"),
                        support_url=self.item.get("SupportUrl"),
                        tags=self.item.get("Tags", []),
                        uid=self.item.get("Name"),
                    )
                    portfolio_tasks.append(
                        associate_product_with_portfolio_task.AssociateProductWithPortfolioTask(
                            region=region,
                            portfolio_args=portfolio_args,
                            product_args=product_args,
                        )
                    )

            if len(portfolio_tasks) > 0:
                required["portfolio_tasks"] = portfolio_tasks
        return required

    def api_calls_used(self):
        return [
            f"cloudformation.create_or_update_{constants.HOME_REGION}",
        ]

    def run(self):
        inputs = self.input()
        template = inputs.get("template").open().read()
        if self.pipeline_type == constants.PIPELINE_MODE_COMBINED:
            friendly_uid = f"{self.category}--{self.name}"
        elif self.pipeline_type == constants.PIPELINE_MODE_SPILT:
            friendly_uid = (
                f"{self.category}--{self.name}-{self.versions[0].get('Name')}"
            )

        tags = [dict(Key="ServiceCatalogFactory:Actor", Value="Generated",)]
        if self.should_pipelines_inherit_tags:
            tags += list(self.initialiser_stack_tags)

        for tag in self.tags:
            tags.append(dict(Key=tag.get("Key"), Value=tag.get("Value"),))

        with self.client("cloudformation") as cloudformation:
            cloudformation.create_or_update(
                StackName=friendly_uid, TemplateBody=template, Tags=tags,
            )
        self.write_output(self.params_for_results_display())
