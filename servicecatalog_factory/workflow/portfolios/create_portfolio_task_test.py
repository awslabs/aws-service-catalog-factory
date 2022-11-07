#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from unittest import skip
from servicecatalog_factory.workflow import tasks_unit_tests_helper


class CreatePortfolioTaskTest(tasks_unit_tests_helper.FactoryTaskUnitTest):
    region = "region"
    portfolio_name = "portfolio_name"
    description = "description"
    provider_name = "provider_name"
    tags = []

    def setUp(self) -> None:
        from servicecatalog_factory.workflow.portfolios import create_portfolio_task

        self.module = create_portfolio_task

        self.sut = self.module.CreatePortfolioTask(
            **self.minimal_common_params,
            region=self.region,
            portfolio_name=self.portfolio_name,
            description=self.description,
            provider_name=self.provider_name,
            tags=self.tags,
        )

        self.wire_up_mocks()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "region": self.region,
            "portfolio_name": self.portfolio_name,
            "task_reference": self.task_reference,
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
