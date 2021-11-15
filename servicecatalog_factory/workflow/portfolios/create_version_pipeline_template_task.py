#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import json

import jinja2
import luigi

from servicecatalog_factory import constants
from servicecatalog_factory import utils
from servicecatalog_factory.template_builder import product_template_factory
from servicecatalog_factory.workflow.portfolios.create_product_task import (
    CreateProductTask,
)
from servicecatalog_factory.workflow.tasks import FactoryTask, logger


class CreateVersionPipelineTemplateTask(FactoryTask):
    all_regions = luigi.ListParameter()
    version = luigi.DictParameter()
    product = luigi.DictParameter()

    provisioner = luigi.DictParameter()
    template = luigi.DictParameter()

    factory_version = luigi.Parameter()

    products_args_by_region = luigi.DictParameter()

    tags = luigi.ListParameter()

    def params_for_results_display(self):
        return {
            "version": self.version.get("Name"),
            "product": self.product.get("Name"),
            "type": self.provisioner.get("Type"),
        }

    def output(self):
        return luigi.LocalTarget(
            f"output/CreateVersionPipelineTemplateTask/"
            f"{self.product.get('Name')}_{self.version.get('Name')}.template.yaml"
        )

    def requires(self):
        create_products_tasks = {}
        for region, product_args_by_region in self.products_args_by_region.items():
            create_products_tasks[region] = CreateProductTask(**product_args_by_region)
        return {
            "create_products_tasks": create_products_tasks,
        }

    def handle_terraform_provisioner(
        self, product_ids_by_region, friendly_uid, tags, source
    ):
        template = utils.ENV.get_template(constants.PRODUCT_TERRAFORM)
        rendered = template.render(
            friendly_uid=f"{friendly_uid}-{self.version.get('Name')}",
            version=self.version,
            product=self.product,
            Options=utils.merge(
                self.product.get("Options", {}), self.version.get("Options", {})
            ),
            Source=source,
            ALL_REGIONS=self.all_regions,
            product_ids_by_region=product_ids_by_region,
            TF_VARS=" ".join(self.provisioner.get("TFVars", [])),
            FACTORY_VERSION=self.factory_version,
            tags=tags,
        )
        rendered = jinja2.Template(rendered).render(
            friendly_uid=f"{friendly_uid}-{self.version.get('Name')}",
            version=self.version,
            product=self.product,
            Options=utils.merge(
                self.product.get("Options", {}), self.version.get("Options", {})
            ),
            Source=utils.merge(
                self.product.get("Source", {}), self.version.get("Source", {})
            ),
            ALL_REGIONS=self.all_regions,
            product_ids_by_region=product_ids_by_region,
            TF_VARS=" ".join(self.provisioner.get("TFVars", [])),
            FACTORY_VERSION=self.factory_version,
        )
        return rendered

    def can_use_code_pipeline(self, product_ids_by_region):
        for region, details in product_ids_by_region.items():
            if region not in constants.CODEPIPELINE_SUPPORTED_REGIONS:
                return False
        return True

    def handle_cloudformation_provisioner(
        self, product_ids_by_region, friendly_uid, tags, source
    ):
        with self.client("s3") as s3:
            s3.put_object(
                Bucket=f"sc-factory-artifacts-{self.factory_account_id}-{self.factory_region}",
                Key=f"cloudformation/{self.product.get('Name')}/product_ids.json",
                Body=json.dumps(product_ids_by_region),
            )
            s3.put_object(
                Bucket=f"sc-factory-artifacts-{self.factory_account_id}-{self.factory_region}",
                Key=f"cloudformation/{self.product.get('Name')}/{self.version.get('Name')}/template.json",
                Body=json.dumps(utils.unwrap(self.template)),
            )

        template = utils.ENV.get_template(constants.PRODUCT_CLOUDFORMATION)

        stages = utils.merge(
            self.product.get("Stages", {}), self.version.get("Stages", {})
        )

        if stages.get("Package") is None:
            stages["Package"] = dict(
                BuildSpecImage=self.version.get(
                    "BuildSpecImage",
                    self.product.get(
                        "BuildSpecImage", constants.PACKAGE_BUILD_SPEC_IMAGE_DEFAULT,
                    ),
                ),
                BuildSpec=self.version.get(
                    "BuildSpec",
                    self.product.get("BuildSpec", constants.PACKAGE_BUILD_SPEC_DEFAULT),
                ),
            )
        can_use_code_pipeline = str(self.can_use_code_pipeline(product_ids_by_region))

        rendered = template.render(
            friendly_uid=f"{friendly_uid}-{self.version.get('Name')}",
            version=self.version,
            product=self.product,
            template_format=self.provisioner.get("Format", "yaml"),
            Options=utils.merge(
                self.product.get("Options", {}), self.version.get("Options", {})
            ),
            Source=source,
            Stages=stages,
            ALL_REGIONS=self.all_regions,
            product_ids_by_region=product_ids_by_region,
            FACTORY_VERSION=self.factory_version,
            tags=tags,
            PARTITION=constants.PARTITION,
            CAN_USE_CODE_PIPELINE=can_use_code_pipeline,
        )
        rendered = jinja2.Template(rendered).render(
            friendly_uid=f"{friendly_uid}-{self.version.get('Name')}",
            version=self.version,
            product=self.product,
            Options=utils.merge(
                self.product.get("Options", {}), self.version.get("Options", {})
            ),
            Source=source,
            Stages=stages,
            ALL_REGIONS=self.all_regions,
            product_ids_by_region=product_ids_by_region,
            PARTITION=constants.PARTITION,
            CAN_USE_CODE_PIPELINE=can_use_code_pipeline,
        )
        return rendered

    def run(self):
        logger_prefix = f"{self.product.get('Name')}-{self.version.get('Name')}"
        logger.info(f"{logger_prefix} - Getting product id")

        product_ids_by_region = {}
        friendly_uid = None

        tags = [
            {"Key": tag.get("Key"), "Value": tag.get("Value"),} for tag in self.tags
        ]

        source = utils.merge(
            self.product.get("Source", {}), self.version.get("Source", {})
        )

        for region, product_details_content in (
            self.input().get("create_products_tasks").items()
        ):
            product_details = json.loads(product_details_content.open("r").read())
            product_ids_by_region[region] = product_details.get("ProductId")
            friendly_uid = product_details.get("uid")

        if self.template.get("Name"):
            with self.client("s3") as s3:
                s3.put_object(
                    Bucket=f"sc-factory-artifacts-{self.factory_account_id}-{self.factory_region}",
                    Key=f"{self.template.get('Name')}/{self.template.get('Version')}/{self.product.get('Name')}/product_ids.json",
                    Body=json.dumps(product_ids_by_region),
                )
                s3.put_object(
                    Bucket=f"sc-factory-artifacts-{self.factory_account_id}-{self.factory_region}",
                    Key=f"{self.template.get('Name')}/{self.template.get('Version')}/{self.product.get('Name')}/{self.version.get('Name')}/template.json",
                    Body=json.dumps(utils.unwrap(self.template)),
                )
            rendered = product_template_factory.get(
                self.template.get("Name"), self.template.get("Version")
            ).render(
                self.template,
                self.product.get("Name"),
                self.version.get("Name"),
                self.version.get("Description", self.product.get("Description")),
                source,
                product_ids_by_region,
                tags,
                friendly_uid,
            )

        elif self.provisioner.get("Type") == "CloudFormation":
            rendered = self.handle_cloudformation_provisioner(
                product_ids_by_region, friendly_uid, tags, source
            )

        elif self.provisioner.get("Type") == "Terraform":
            rendered = self.handle_terraform_provisioner(
                product_ids_by_region, friendly_uid, tags, source
            )

        else:
            raise Exception(f"Unknown type: {self.type}")

        with self.output().open("w") as output_file:
            output_file.write(rendered)
