#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from unittest import skip
from servicecatalog_factory.workflow import tasks_unit_tests_helper


class AssociateProductWithPortfolioTaskTest(
    tasks_unit_tests_helper.FactoryTaskUnitTest
):
    region = "region"
    create_product_task_ref = "create_product_task_ref"
    create_portfolio_task_ref = "create_portfolio_task_ref"

    def setUp(self) -> None:
        from servicecatalog_factory.workflow.portfolios import (
            associate_product_with_portfolio_task,
        )

        self.module = associate_product_with_portfolio_task

        self.sut = self.module.AssociateProductWithPortfolioTask(
            **self.minimal_common_params,
            region=self.region,
            create_product_task_ref=self.create_product_task_ref,
            create_portfolio_task_ref=self.create_portfolio_task_ref,
        )

        self.wire_up_mocks()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "region": self.region,
            "create_product_task_ref": self.create_product_task_ref,
            "create_portfolio_task_ref": self.create_portfolio_task_ref,
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
