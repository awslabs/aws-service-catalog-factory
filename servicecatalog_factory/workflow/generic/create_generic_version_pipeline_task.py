#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from servicecatalog_factory.template_builder import product_template_factory
from servicecatalog_factory.workflow import tasks
import luigi
from luigi.util import inherits


class CreateGenericVersionPipelineTemplateTask(tasks.FactoryTask):
    category = luigi.Parameter()
    name = luigi.Parameter()
    version = luigi.Parameter()
    source = luigi.DictParameter()
    options = luigi.DictParameter()
    stages = luigi.DictParameter()

    def params_for_results_display(self):
        return {
            "category": self.category,
            "name": self.name,
            "version": self.version,
        }

    def output(self):
        return luigi.LocalTarget(
            f"output/{self.__class__.__name__}/"
            f"{self.category}-{self.name}-{self.version}.template.yaml"
        )

    def run(self):
        template = product_template_factory.get_v2(self.category)
        builder = template.build(
            self.name, self.version, self.source, self.options, self.stages
        )
        self.write_output_raw(builder.to_yaml(clean_up=True, long_form=True))


@inherits(CreateGenericVersionPipelineTemplateTask)
class CreateGenericVersionPipelineTask(tasks.FactoryTask):
    category = luigi.Parameter()
    name = luigi.Parameter()
    version = luigi.Parameter()
    source = luigi.DictParameter()
    options = luigi.DictParameter()
    stages = luigi.DictParameter()

    def params_for_results_display(self):
        return {
            "category": self.category,
            "name": self.name,
            "version": self.version,
        }

    def requires(self):
        return self.clone(CreateGenericVersionPipelineTemplateTask)

    def run(self):
        template = self.input().open().read()
        friendly_uid = f"{self.category}--{self.name}-{self.version}"
        with self.client("cloudformation") as cloudformation:
            cloudformation.create_or_update(
                StackName=friendly_uid, TemplateBody=template,
            )
        self.write_output(self.params_for_results_display())
