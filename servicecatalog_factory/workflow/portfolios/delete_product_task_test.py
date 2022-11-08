#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from unittest import skip
from servicecatalog_factory.workflow import tasks_unit_tests_helper


class DeleteProductTaskTest(tasks_unit_tests_helper.FactoryTaskUnitTest):
    uid = "uid"
    region = "region"
    name = "name"
    pipeline_mode = "pipeline_mode"

    def setUp(self) -> None:
        from servicecatalog_factory.workflow.portfolios import delete_product_task

        self.module = delete_product_task

        self.sut = self.module.DeleteProductTask(
            **self.minimal_common_params,
            uid=self.uid,
            region=self.region,
            name=self.name,
            pipeline_mode=self.pipeline_mode,
        )

        self.wire_up_mocks()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "region": self.region,
            "uid": self.uid,
            "name": self.name,
            "pipeline_mode": self.pipeline_mode,
        }

        # exercise
        actual_result = self.sut.params_for_results_display()

        # verify
        self.assertEqual(expected_result, actual_result)

    @skip
    def test_run(self):
        # setup
        # exercise
        actual_result = self.sut.run()

        # verify
        raise NotImplementedError()
