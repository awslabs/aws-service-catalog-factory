#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import cfn_tools
import luigi

from servicecatalog_factory.workflow.portfolios.create_version_pipeline_template_task import (
    CreateVersionPipelineTemplateTask,
)
from servicecatalog_factory.workflow.tasks import FactoryTask


class CreateVersionPipelineTask(FactoryTask):
    all_regions = luigi.ListParameter()
    version = luigi.DictParameter()
    product = luigi.DictParameter()

    provisioner = luigi.DictParameter()
    template = luigi.DictParameter()

    products_args_by_region = luigi.DictParameter()

    factory_version = luigi.Parameter()
    region = luigi.Parameter()

    tags = luigi.ListParameter()

    def params_for_results_display(self):
        return {
            "version": self.version.get("Name"),
            "product": self.product.get("Name"),
        }

    def output(self):
        return luigi.LocalTarget(
            f"output/CreateVersionPipelineTask/"
            f"{self.product.get('Name')}_{self.version.get('Name')}.template.yaml"
        )

    def requires(self):
        return CreateVersionPipelineTemplateTask(
            all_regions=self.all_regions,
            version=self.version,
            product=self.product,
            provisioner=self.provisioner,
            template=self.template,
            products_args_by_region=self.products_args_by_region,
            factory_version=self.factory_version,
            tags=self.tags,
        )

    def run(self):
        template_contents = self.input().open("r").read()
        template = cfn_tools.load_yaml(template_contents)
        friendly_uid = template.get("Description").split("\n")[0]
        self.info(f"creating the stack: {friendly_uid}")
        tags = []
        for tag in self.tags:
            tags.append(
                {"Key": tag.get("Key"), "Value": tag.get("Value"),}
            )
        with self.client("cloudformation") as cloudformation:
            if self.template.get("Name"):
                response = cloudformation.create_or_update(
                    StackName=friendly_uid, TemplateBody=template_contents, Tags=tags,
                )
            elif self.provisioner.get("Type") == "CloudFormation":
                response = cloudformation.create_or_update(
                    StackName=friendly_uid, TemplateBody=template_contents, Tags=tags,
                )
            elif self.provisioner.get("Type") == "Terraform":
                response = cloudformation.create_or_update(
                    StackName=friendly_uid,
                    TemplateBody=template_contents,
                    Parameters=[
                        {
                            "ParameterKey": "Version",
                            "ParameterValue": self.factory_version,
                            "UsePreviousValue": False,
                        },
                    ],
                    Tags=tags,
                )
            else:
                raise Exception("did not do anything")

        self.write_output(response)

        self.info(f"Finished")
