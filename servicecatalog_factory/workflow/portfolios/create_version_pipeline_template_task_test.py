#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from unittest import mock, skip
from servicecatalog_factory.workflow import tasks_unit_tests_helper

import os

class CreateVersionPipelineTemplateTaskTest(
    tasks_unit_tests_helper.FactoryTaskUnitTest
):
    version = {}
    all_regions = ["region"]
    version = {}
    product = {}
    provisioner = {"Type": "Cloudformation"}
    template = {}
    factory_version = "factory_version"
    products_args_by_region = {}
    tags = []

    def setUp(self) -> None:
        from servicecatalog_factory.workflow.portfolios import (
            create_version_pipeline_template_task,
        )

        self.module = create_version_pipeline_template_task

        self.sut = self.module.CreateVersionPipelineTemplateTask(
            all_regions=self.all_regions,
            version=self.version,
            product=self.product,
            provisioner=self.provisioner,
            template=self.template,
            factory_version=self.factory_version,
            products_args_by_region=self.products_args_by_region,
            tags=self.tags,
        )

        self.wire_up_mocks()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "version": self.version.get("Name"),
            "product": self.product.get("Name"),
            "type": self.provisioner.get("Type"),
        }

        # exercise
        actual_result = self.sut.params_for_results_display()

        # verify
        self.assertEqual(expected_result, actual_result)

    
    @mock.patch.dict(os.environ, {"ACCOUNT_ID": "account_id", "REGION": "region"}, clear=True)
    def test_handle_cloudformation_provisioner_format(self):
        for provisioner_format in [None, "json", "yaml"]:
            # setup
            self.sut.provisioner = {"Type": "Cloudformation", "Format": provisioner_format}

            # exercise
            rendered = self.sut.handle_cloudformation_provisioner(
                product_ids_by_region={},
                friendly_uid="",
                tags=[],
                source={"Provider": "codecommit", "Configuration": { "PollForSourceChanges": "False"} }
            )

            # verify
            self.assertIn(f"product.template.{provisioner_format}", rendered)
            self.assertNotIn(f"product.template.{'yaml' if provisioner_format == 'json' else 'json'}", rendered)

    @skip
    def test_requires(self):
        # setup
        # exercise
        actual_result = self.sut.requires()

        # verify
        raise NotImplementedError()

    @skip
    def test_run(self):
        # setup
        # exercise
        actual_result = self.sut.run()

        # verify
        raise NotImplementedError()
