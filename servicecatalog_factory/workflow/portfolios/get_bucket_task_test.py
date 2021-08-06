#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from unittest import skip
from servicecatalog_factory.workflow import tasks_unit_tests_helper


class GetBucketTaskTest(tasks_unit_tests_helper.FactoryTaskUnitTest):
    region = "region"

    def setUp(self) -> None:
        from servicecatalog_factory.workflow.portfolios import get_bucket_task

        self.module = get_bucket_task

        self.sut = self.module.GetBucketTask(region=self.region)

        self.wire_up_mocks()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "region": self.region,
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
