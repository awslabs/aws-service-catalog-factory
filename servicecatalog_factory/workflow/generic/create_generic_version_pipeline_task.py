#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
from servicecatalog_factory import constants
from servicecatalog_factory.template_builder.pipeline import pipeline_template_builder
from servicecatalog_factory.workflow import tasks
import luigi


class CreateGenericCombinedPipelineTask(tasks.FactoryTask):
    region = luigi.Parameter()
    pipeline_type = luigi.Parameter()
    category = luigi.Parameter()
    name = luigi.Parameter()
    stack_name = luigi.Parameter()
    item = luigi.DictParameter()
    versions = luigi.ListParameter()
    options = luigi.DictParameter()
    stages = luigi.DictParameter()
    tags = luigi.ListParameter()

    def params_for_results_display(self):
        return {"task_reference": self.task_reference}

    def make_template(self):
        template = pipeline_template_builder.PipelineTemplate(
            self.category, constants.PIPELINE_MODE_COMBINED
        )
        builder = template.build(
            self.name, self.item, self.versions, self.options, self.stages
        )
        return builder.to_json()

    def run(self):
        template = self.make_template()
        if self.stack_name:
            friendly_uid = self.stack_name
        else:
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

        with self.regional_client("cloudformation") as cloudformation:
            cloudformation.create_or_update(
                StackName=friendly_uid, TemplateBody=template, Tags=tags,
            )
        self.write_output(self.params_for_results_display())
