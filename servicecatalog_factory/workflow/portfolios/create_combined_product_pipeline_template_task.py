#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import json

import jinja2
import luigi

from servicecatalog_factory import config
from servicecatalog_factory import constants
from servicecatalog_factory import utils
from servicecatalog_factory.workflow.portfolios.create_product_task import (
    CreateProductTask,
)
from servicecatalog_factory.workflow.tasks import FactoryTask


class CreateCombinedProductPipelineTemplateTask(FactoryTask):
    all_regions = luigi.ListParameter()
    product = luigi.DictParameter()
    products_args_by_region = luigi.DictParameter()
    factory_version = luigi.Parameter()

    def params_for_results_display(self):
        return {
            "product": self.product.get("Name"),
        }

    def output(self):
        return luigi.LocalTarget(
            f"output/CreateCombinedProductPipelineTemplateTask/"
            f"{self.product.get('Name')}.template.yaml"
        )

    def requires(self):
        create_products_tasks = {}
        for region, product_args_by_region in self.products_args_by_region.items():
            create_products_tasks[region] = CreateProductTask(**product_args_by_region)
        return {
            "create_products_tasks": create_products_tasks,
        }

    def run(self):
        product_ids_by_region = {}
        friendly_uid = None

        for region, product_details_content in (
            self.input().get("create_products_tasks").items()
        ):
            product_details = json.loads(product_details_content.open("r").read())
            product_ids_by_region[region] = product_details.get("ProductId")
            friendly_uid = product_details.get("uid")

        provisioner_type = self.product.get("Provisioner", {}).get(
            "Type", constants.PROVISIONERS_DEFAULT
        )
        template_format = self.product.get("Provisioner", {}).get(
            "Format", constants.TEMPLATE_FORMATS_DEFAULT
        )

        versions = list()
        for version in self.product.get("Versions"):
            if (
                version.get("Status", constants.STATUS_DEFAULT)
                == constants.STATUS_ACTIVE
            ):
                versions.append(version)

        if provisioner_type == constants.PROVISIONERS_CLOUDFORMATION:
            template = utils.ENV.get_template(constants.PRODUCT_COMBINED_CLOUDFORMATION)
            rendered = template.render(
                friendly_uid=friendly_uid,
                product=self.product,
                template_format=template_format,
                Options=self.product.get("Options", {}),
                Versions=versions,
                ALL_REGIONS=self.all_regions,
                product_ids_by_region=product_ids_by_region,
                FACTORY_VERSION=self.factory_version,
                VERSION=config.get_stack_version(),
                tags=self.product.get("Tags"),
            )
            rendered = jinja2.Template(rendered).render(
                friendly_uid=friendly_uid,
                product=self.product,
                Options=self.product.get("Options", {}),
                Versions=versions,
                ALL_REGIONS=self.all_regions,
                product_ids_by_region=product_ids_by_region,
            )

        else:
            raise Exception(f"Unknown/unsupported provisioner type: {provisioner_type}")

        self.write_output_raw(rendered)
