#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from unittest import skip
from servicecatalog_factory.workflow import tasks_unit_tests_helper


class AssociateProductWithPortfolioTaskTest(
    tasks_unit_tests_helper.FactoryTaskUnitTest
):
    region = "region"
    portfolio_args = {}
    product_args = {}

    def setUp(self) -> None:
        from servicecatalog_factory.workflow.portfolios import (
            associate_product_with_portfolio_task,
        )

        self.module = associate_product_with_portfolio_task

        self.sut = self.module.AssociateProductWithPortfolioTask(
            region=self.region,
            portfolio_args=self.portfolio_args,
            product_args=self.product_args,
        )

        self.wire_up_mocks()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "region": self.region,
            "portfolio": f"{self.portfolio_args.get('portfolio_group_name')}-{self.portfolio_args.get('display_name')}",
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
