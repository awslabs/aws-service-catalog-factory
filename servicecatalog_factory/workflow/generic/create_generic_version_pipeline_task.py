#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
from servicecatalog_factory import constants
from servicecatalog_factory.template_builder import pipeline_template_builder
from servicecatalog_factory.workflow import tasks
import luigi
from luigi.util import inherits


class CreateGenericCombinedPipelineTemplateTask(tasks.FactoryTask):
    pipeline_type = luigi.Parameter()
    category = luigi.Parameter()
    name = luigi.Parameter()
    item = luigi.DictParameter()
    versions = luigi.ListParameter()
    options = luigi.DictParameter()
    stages = luigi.DictParameter()
    tags = luigi.ListParameter()

    def params_for_results_display(self):
        versions = ",".join([version.get("Name") for version in self.versions])
        return {
            "category": self.category,
            "name": self.name,
            "versions": versions,
        }

    def output(self):
        versions = ",".join([version.get("Name") for version in self.versions])
        return luigi.LocalTarget(
            f"output/{self.__class__.__name__}/"
            f"{self.category}-{self.name}-{versions}.template.json"
        )

    def run(self):
        template = pipeline_template_builder.PipelineTemplate(
            self.category, constants.PIPELINE_MODE_COMBINED
        )
        builder = template.build(
            self.name, self.item, self.versions, self.options, self.stages
        )
        self.write_output_raw(builder.to_json())


@inherits(CreateGenericCombinedPipelineTemplateTask)
class CreateGenericCombinedPipelineTask(tasks.FactoryTask):
    pipeline_type = luigi.Parameter()
    category = luigi.Parameter()
    name = luigi.Parameter()
    item = luigi.DictParameter()
    versions = luigi.ListParameter()
    options = luigi.DictParameter()
    stages = luigi.DictParameter()
    tags = luigi.ListParameter()

    def params_for_results_display(self):
        versions = ",".join([version.get("Name") for version in self.versions])
        return {"category": self.category, "name": self.name, "versions": versions}

    def requires(self):
        return self.clone(CreateGenericCombinedPipelineTemplateTask)

    def api_calls_used(self):
        return [
            f"cloudformation.create_or_update_{constants.HOME_REGION}",
        ]

    def run(self):
        template = self.input().open().read()
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

        with self.client("cloudformation") as cloudformation:
            cloudformation.create_or_update(
                StackName=friendly_uid, TemplateBody=template, Tags=tags,
            )
        self.write_output(self.params_for_results_display())
