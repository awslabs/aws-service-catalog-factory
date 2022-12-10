#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import troposphere as t
from deepmerge import always_merger
from troposphere import codepipeline

from servicecatalog_factory.template_builder import base_template
from servicecatalog_factory.template_builder.pipeline.build import BuildTemplateMixin
from servicecatalog_factory.template_builder.pipeline.deploy import DeployTemplateMixin
from servicecatalog_factory.template_builder.pipeline.package import (
    PackageTemplateMixin,
)
from servicecatalog_factory.template_builder.pipeline.source import (
    get_source_action_for_source,
)
from servicecatalog_factory.template_builder.pipeline.test import TestTemplateMixin


def add_custom_provider_details_to_tpl(source, tpl):
    if source.get("Provider", "").lower() == "custom":
        if source.get("Configuration").get("GitWebHookIpAddress") is not None:
            webhook = codepipeline.Webhook(
                "Webhook",
                Authentication="IP",
                TargetAction="Source",
                AuthenticationConfiguration=codepipeline.WebhookAuthConfiguration(
                    AllowedIPRange=source.get("Configuration").get(
                        "GitWebHookIpAddress"
                    )
                ),
                Filters=[
                    codepipeline.WebhookFilterRule(
                        JsonPath="$.changes[0].ref.id",
                        MatchEquals="refs/heads/{Branch}",
                    )
                ],
                TargetPipelineVersion=1,
                TargetPipeline=t.Sub("${AWS::StackName}-pipeline"),
            )
            tpl.add_resource(webhook)
            values_for_sub = {
                "GitUrl": source.get("Configuration").get("GitUrl"),
                "WebhookUrl": t.GetAtt(webhook, "Url"),
            }
        else:
            values_for_sub = {
                "GitUrl": source.get("Configuration").get("GitUrl"),
                "WebhookUrl": "GitWebHookIpAddress was not defined in manifests Configuration",
            }
        output_to_add = t.Output("WebhookUrl")
        output_to_add.Value = t.Sub("${GitUrl}||${WebhookUrl}", **values_for_sub)
        output_to_add.Export = t.Export(t.Sub("${AWS::StackName}-pipeline"))
        tpl.add_output(output_to_add)


class PipelineTemplate(
    TestTemplateMixin, BuildTemplateMixin, PackageTemplateMixin, DeployTemplateMixin
):
    def __init__(self, category, pipeline_mode) -> None:
        super().__init__()
        self.category = category
        self.pipeline_mode = pipeline_mode

    def build(self, name, item, versions, options, stages) -> t.Template:
        tpl = t.Template()
        pipeline_stages = list()

        build_stage_input_artifact_name = base_template.SOURCE_OUTPUT_ARTIFACT
        test_stage_input_artifact_name = base_template.SOURCE_OUTPUT_ARTIFACT
        package_stage_input_artifact_name = base_template.SOURCE_OUTPUT_ARTIFACT
        deploy_stage_input_artifact_name = base_template.PACKAGE_OUTPUT_ARTIFACT

        pipeline_stages.append(self.generate_source_stage(tpl, item, versions))
        # if self.has_a_parse_stage(options):
        #     pipeline_stages.append(
        #         self.generate_parse_stage()
        #     )
        if self.has_a_build_stage(stages):
            test_stage_input_artifact_name = base_template.BUILD_OUTPUT_ARTIFACT
            package_stage_input_artifact_name = base_template.BUILD_OUTPUT_ARTIFACT

            pipeline_stages.append(
                self.generate_build_stage(
                    tpl, versions, stages, build_stage_input_artifact_name
                )
            )

        if self.has_a_test_stage(stages):
            if self.is_cloudformation_based():
                # need to collect generated .txt files
                package_stage_input_artifact_name = (
                    base_template.VALIDATE_OUTPUT_ARTIFACT
                )

            pipeline_stages.append(
                self.generate_test_stage(
                    tpl, item, versions, options, stages, test_stage_input_artifact_name
                )
            )

        pipeline_stages.append(
            self.generate_package_stage(
                tpl, item, versions, options, stages, package_stage_input_artifact_name
            )
        )
        pipeline_stages.append(
            self.generate_deploy_stage(
                tpl, item, versions, stages, deploy_stage_input_artifact_name
            )
        )

        tpl.add_resource(
            codepipeline.Pipeline(
                "Pipeline",
                RoleArn=t.Sub(
                    "arn:${AWS::Partition}:iam::${AWS::AccountId}:role/servicecatalog-product-factory/CodePipelineRole"
                ),
                Stages=pipeline_stages,
                Name=t.Sub("${AWS::StackName}-pipeline"),
                ArtifactStore=codepipeline.ArtifactStore(
                    Type="S3",
                    Location=t.Sub(
                        "sc-factory-artifacts-${AWS::AccountId}-${AWS::Region}"
                    ),
                ),
                RestartExecutionOnUpdate=False,
            ),
        )
        return tpl

    def is_cloudformation_based(self):
        return self.category in ["stack", "products", "product"]

    def has_a_parse_stage(self, options):
        if self.is_cloudformation_based():
            return options.get("ShouldParseAsJinja2Template", False)
        return False

    def generate_source_stage(self, tpl, item, versions) -> codepipeline.Stages:
        actions = list()
        for version in versions:
            source = always_merger.merge(
                item.get("Source", {}), version.get("Source", {})
            )
            add_custom_provider_details_to_tpl(source, tpl)
            actions.append(
                get_source_action_for_source(
                    source, source_name_suffix=f'_{version.get("Name")}'
                )
            )
        return codepipeline.Stages(Name="Source", Actions=actions,)
