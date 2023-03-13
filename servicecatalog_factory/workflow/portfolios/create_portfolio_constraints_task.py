#  Copyright 2023 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
from servicecatalog_factory import constants
from servicecatalog_factory.workflow.tasks import FactoryTask
import luigi
import re
import troposphere as t
from troposphere import servicecatalog

retry_max_attempts = 50


class CreatePortfolioConstraintsTask(FactoryTask):
    region = luigi.Parameter()
    create_portfolio_task_ref = luigi.Parameter()
    portfolio_name = luigi.Parameter()
    constraints = luigi.DictParameter()
    tags = luigi.ListParameter()

    factory_version = luigi.Parameter()

    def get_products_and_their_versions(self, portfolio_id):
        products = dict()
        with self.regional_client(
            "servicecatalog", retry_max_attempts=retry_max_attempts
        ) as servicecatalog:
            paginator = servicecatalog.get_paginator("search_products_as_admin")
            for page in paginator.paginate(
                PortfolioId=portfolio_id, ProductSource="ACCOUNT",
            ):
                for product_view_detail in page.get("ProductViewDetails", []):
                    product_arn = product_view_detail.get("ProductARN")
                    product_view_summary = product_view_detail.get("ProductViewSummary")
                    product_view_summary["ProductArn"] = product_arn
                    product_view_summary["Versions"] = dict()
                    product_id = product_view_summary.get("ProductId")
                    product_name = product_view_summary.get("Name")
                    products[product_name] = product_view_summary
                    provisioning_artifact_summaries = servicecatalog.describe_product_as_admin(
                        Id=product_view_summary.get("ProductId"),
                    ).get(
                        "ProvisioningArtifactSummaries"
                    )
                    for (
                        provisioning_artifact_summary
                    ) in provisioning_artifact_summaries:
                        version_name = provisioning_artifact_summary.get("Name")
                        provisioning_artifact_detail = servicecatalog.describe_provisioning_artifact(
                            ProductId=product_id, ProvisioningArtifactName=version_name,
                        ).get(
                            "ProvisioningArtifactDetail"
                        )
                        provisioning_artifact_summary[
                            "Active"
                        ] = provisioning_artifact_detail.get("Active")
                        provisioning_artifact_summary[
                            "Guidance"
                        ] = provisioning_artifact_detail.get("Guidance")
                        product_view_summary["Versions"][
                            version_name
                        ] = provisioning_artifact_summary
        return products

    def run(self):
        portfolio_details = self.get_output_from_reference_dependency(
            self.create_portfolio_task_ref
        )
        portfolio_id = portfolio_details.get("Id")
        products_and_their_versions = self.get_products_and_their_versions(portfolio_id)

        tpl = t.Template()
        tpl.description = (
            """resource constraints """
            + self.portfolio_name
            + '''
            {"version": "'''
            + constants.VERSION
            + """", "framework": "servicecatalog-factory", "role": "portfolio-constraints"}"""
        )

        resource_update_constraints = self.constraints.get("ResourceUpdate")

        if resource_update_constraints:
            for resource_update_constraint in resource_update_constraints:
                products_to_constrain = list()
                constraint = resource_update_constraint.get(
                    "Products", resource_update_constraint.get("Product")
                )
                if isinstance(constraint, tuple):
                    for p in constraint:
                        products_to_constrain.append(p)
                elif isinstance(constraint, str):
                    products_to_constrain.append(constraint)
                else:
                    raise Exception(
                        f"Unexpected launch constraint type {type(constraint)}"
                    )

                validate_tag_update = resource_update_constraint.get(
                    "TagUpdateOnProvisionedProduct"
                )
                for product_to_constrain in products_to_constrain:
                    for (
                        product_name,
                        product_details,
                    ) in products_and_their_versions.items():
                        if re.match(product_to_constrain, product_name,):
                            product_id = product_details.get("ProductId")
                            tpl.add_resource(
                                servicecatalog.ResourceUpdateConstraint(
                                    f"L{portfolio_id}B{product_id}C".replace("-", ""),
                                    PortfolioId=portfolio_id,
                                    Description=f"TagUpdate = {validate_tag_update}",
                                    ProductId=product_id,
                                    TagUpdateOnProvisionedProduct=validate_tag_update,
                                )
                            )

        tags = [dict(Key="ServiceCatalogFactory:Actor", Value="Generated",)]
        if self.should_pipelines_inherit_tags:
            tags += list(self.initialiser_stack_tags)

        stack_name = "-".join([self.portfolio_name, "constraints"])
        with self.regional_client("cloudformation") as cloudformation:
            cloudformation.create_or_update(
                StackName=stack_name,
                TemplateBody=tpl.to_yaml(clean_up=True, long_form=True),
                Tags=tags,
            )
        self.write_output_raw("{}")
