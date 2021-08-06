#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from unittest import skip
from servicecatalog_factory.workflow import tasks_unit_tests_helper


class CreateVersionPipelineTaskTest(tasks_unit_tests_helper.FactoryTaskUnitTest):
    all_regions = []
    version = {}
    product = {}
    provisioner = {}
    template = {}
    products_args_by_region = {}
    factory_version = "factory_version"
    region = "region"
    tags = []

    def setUp(self) -> None:
        from servicecatalog_factory.workflow.portfolios import (
            create_version_pipeline_task,
        )

        self.module = create_version_pipeline_task

        self.sut = self.module.CreateVersionPipelineTask(
            all_regions=self.all_regions,
            version=self.version,
            product=self.product,
            provisioner=self.provisioner,
            template=self.template,
            products_args_by_region=self.products_args_by_region,
            factory_version=self.factory_version,
            region=self.region,
            tags=self.tags,
        )

        self.wire_up_mocks()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "version": self.version.get("Name"),
            "product": self.product.get("Name"),
        }

        # exercise
        actual_result = self.sut.params_for_results_display()

        # verify
        self.assertEqual(expected_result, actual_result)

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
