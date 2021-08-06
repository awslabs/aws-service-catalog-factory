#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from unittest import skip
from servicecatalog_factory.workflow import tasks_unit_tests_helper


class CreateCodeRepoTaskTest(tasks_unit_tests_helper.FactoryTaskUnitTest):
    repository_name = "repository_name"
    branch_name = "branch_name"
    bucket = "bucket"
    key = "key"

    def setUp(self) -> None:
        from servicecatalog_factory.workflow.codecommit import create_code_repo_task

        self.module = create_code_repo_task

        self.sut = self.module.CreateCodeRepoTask(
            repository_name=self.repository_name,
            branch_name=self.branch_name,
            bucket=self.bucket,
            key=self.key,
        )

        self.wire_up_mocks()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "repository_name": self.repository_name,
            "branch_name": self.branch_name,
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
