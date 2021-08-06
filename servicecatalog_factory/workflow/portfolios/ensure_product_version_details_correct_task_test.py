#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from unittest import skip
from servicecatalog_factory.workflow import tasks_unit_tests_helper


class EnsureProductVersionDetailsCorrectTest(
    tasks_unit_tests_helper.FactoryTaskUnitTest
):
    region = "region"
    version = {}
    product_args = {}

    def setUp(self) -> None:
        from servicecatalog_factory.workflow.portfolios import (
            ensure_product_version_details_correct_task,
        )

        self.module = ensure_product_version_details_correct_task

        self.sut = self.module.EnsureProductVersionDetailsCorrect(
            region=self.region, version=self.version, product_args=self.product_args
        )

        self.wire_up_mocks()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "region": self.region,
            "version": self.version.get("Name"),
            "product": self.product_args.get("name"),
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
