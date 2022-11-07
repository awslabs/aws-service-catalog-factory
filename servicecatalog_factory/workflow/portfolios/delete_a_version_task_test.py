#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from unittest import skip
from servicecatalog_factory.workflow import tasks_unit_tests_helper


class DeleteAVersionTaskTest(tasks_unit_tests_helper.FactoryTaskUnitTest):
    product_args = {}
    version = "version"

    def setUp(self) -> None:
        from servicecatalog_factory.workflow.portfolios import delete_a_version_task

        self.module = delete_a_version_task

        self.sut = self.module.DeleteAVersionTask(
            **self.minimal_common_params,
            product_args=self.product_args,
            version=self.version
        )

        self.wire_up_mocks()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "uid": self.product_args.get("uid"),
            "region": self.product_args.get("region"),
            "name": self.product_args.get("name"),
            "version": self.version,
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
