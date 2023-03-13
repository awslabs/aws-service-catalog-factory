#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import json

import luigi

from servicecatalog_factory import constants
from servicecatalog_factory import utils
from servicecatalog_factory.workflow.tasks import FactoryTask
import troposphere as t
from troposphere import s3, servicecatalog


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
            tpl = t.Template()
            tpl.description = (
                """Associations for """
                + self.portfolio_name
                + '''
    {"version": "'''
                + constants.VERSION
                + """", "framework": "servicecatalog-factory", "role": "portfolio-associations"}"""
            )

            tpl.add_condition("ShouldDoAnything", t.Equals(True, False))

            tpl.add_resource(s3.Bucket("NoOp", Condition="ShouldDoAnything"))

            for association in self.associations:
                portfolio_id = create_portfolio_task_output.get("Id")
                if isinstance(association, str):
                    principal_arn = association
                    principal_type = "IAM"
                else:
                    association = utils.unwrap(association)
                    unwrapped_association = utils.unwrap(association)
                    principal_arn = unwrapped_association["PrincipalARN"]
                    principal_type = unwrapped_association["PrincipalType"]

                logical_name = "".join(
                    filter(
                        str.isalnum, f"{portfolio_id}{principal_arn.split(':')[-1]}",
                    )
                )
                tpl.add_resource(
                    servicecatalog.PortfolioPrincipalAssociation(
                        logical_name,
                        PortfolioId=portfolio_id,
                        PrincipalARN=t.Sub(principal_arn),
                        PrincipalType=principal_type,
                    )
                )
            v1_stack_name = "-".join([self.portfolio_name, "associations"])
            v2_stack_name = "-".join([self.portfolio_name, "associations", "v2"])
            tags = [dict(Key="ServiceCatalogFactory:Actor", Value="Generated",)]
            if self.should_pipelines_inherit_tags:
                tags += list(self.initialiser_stack_tags)

            cloudformation.ensure_deleted(StackName=v1_stack_name)

            cloudformation.create_or_update(
                StackName=v2_stack_name,
                TemplateBody=tpl.to_yaml(clean_up=True, long_form=True),
                Tags=tags,
            )
