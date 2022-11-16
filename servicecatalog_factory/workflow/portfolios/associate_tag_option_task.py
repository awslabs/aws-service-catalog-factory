#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import luigi

from servicecatalog_factory.workflow.tasks import FactoryTask


class AssociateTagOptionTask(FactoryTask):
    region = luigi.Parameter()

    create_product_task_ref = luigi.Parameter()
    create_portfolio_task_ref = luigi.Parameter()
    create_tag_option_task_ref = luigi.Parameter()

    def params_for_results_display(self):
        return {
            "region": self.region,
            "create_product_task_ref": self.create_product_task_ref,
            "create_portfolio_task_ref": self.create_portfolio_task_ref,
            "create_tag_option_task_ref": self.create_tag_option_task_ref,
        }

    def run(self):
        with self.regional_client("servicecatalog") as servicecatalog:
            if self.create_portfolio_task_ref:
                portfolio_details = self.get_output_from_reference_dependency(
                    self.create_portfolio_task_ref
                )
                resource_id = portfolio_details.get("Id")
            elif self.create_product_task_ref:
                product_details = self.get_output_from_reference_dependency(
                    self.create_product_task_ref
                )
                resource_id = product_details.get("ProductId")
            else:
                raise Exception("Did not find a resource to associate with")

            tag_option_details = self.get_output_from_reference_dependency(
                self.create_tag_option_task_ref
            )

            try:
                servicecatalog.associate_tag_option_with_resource(
                    ResourceId=resource_id, TagOptionId=tag_option_details.get("Id"),
                )
            except servicecatalog.exceptions.DuplicateResourceException:
                pass
            self.write_output_raw("{}")
