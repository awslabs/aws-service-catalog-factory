#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import cfn_tools
import luigi

from servicecatalog_factory import constants
from servicecatalog_factory.workflow.portfolios.create_combined_product_pipeline_template_task import (
    CreateCombinedProductPipelineTemplateTask,
)
from servicecatalog_factory.workflow.tasks import FactoryTask


class CreateCombinedProductPipelineTask(FactoryTask):
    all_regions = luigi.ListParameter()
    product = luigi.DictParameter()
    products_args_by_region = luigi.DictParameter()
    factory_version = luigi.Parameter()

    def params_for_results_display(self):
        return {
            "product": self.product.get("Name"),
        }

    def requires(self):
        return CreateCombinedProductPipelineTemplateTask(
            all_regions=self.all_regions,
            product=self.product,
            products_args_by_region=self.products_args_by_region,
            factory_version=self.factory_version,
        )

    def run(self):
        template_contents = self.input().open("r").read()
        template = cfn_tools.load_yaml(template_contents)
        friendly_uid = template.get("Description").split("\n")[0]
        self.info(f"creating the stack: {friendly_uid}")
        tags = []

        for tag in self.product.get("Tags"):
            tags.append(
                {"Key": tag.get("Key"), "Value": tag.get("Value"),}
            )
        provisioner = self.product.get("Provisioner", {}).get(
            "Type", constants.PROVISIONERS_DEFAULT
        )
        with self.client("cloudformation") as cloudformation:
            if provisioner == constants.PROVISIONERS_CLOUDFORMATION:
                response = cloudformation.create_or_update(
                    StackName=friendly_uid, TemplateBody=template_contents, Tags=tags,
                )
            else:
                raise Exception(f"Unknown/unsupported provisioner: {provisioner}")

        self.info(f"Finished")
        self.write_output(response)
