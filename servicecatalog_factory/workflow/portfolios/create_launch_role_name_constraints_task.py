#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
from servicecatalog_factory.workflow.tasks import FactoryTask
import luigi
import troposphere as t
from troposphere import servicecatalog as sc


class CreateLaunchRoleNameConstraintsTask(FactoryTask):
    portfolio_name = luigi.Parameter()
    region = luigi.Parameter()
    launch_role_constraints = luigi.ListParameter()

    def params_for_results_display(self):
        return {
            "region": self.region,
            "task_reference": self.task_reference,
        }

    def run(self):
        tpl = t.Template()
        tpl.description = f"Launch role constraints for {self.portfolio_name}"
        for launch_role_constraint in self.launch_role_constraints:
            portfolio_task_ref = launch_role_constraint.get("portfolio_task_ref")
            portfolio_task_output = self.get_output_from_reference_dependency(
                portfolio_task_ref
            )
            product_task_ref = launch_role_constraint.get("product_task_ref")
            product_task_output = self.get_output_from_reference_dependency(
                product_task_ref
            )
            constraint_name = f'{portfolio_task_output.get("Id")}1{product_task_output.get("ProductId")}'.replace(
                "-", ""
            )
            tpl.add_resource(
                sc.LaunchRoleConstraint(
                    constraint_name,
                    LocalRoleName=launch_role_constraint.get("local_role_name"),
                    PortfolioId=portfolio_task_output.get("Id"),
                    ProductId=product_task_output.get("ProductId"),
                )
            )
        template_to_use = tpl.to_yaml()
        with self.regional_client("cloudformation") as cloudformation:
            cloudformation.create_or_update(
                StackName=f"servicecatalog-factory-constraints-launch-role-v3-{self.portfolio_name}",
                TemplateBody=template_to_use,
            )

        self.write_output(dict(template_used=template_to_use))
