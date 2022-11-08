#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from unittest import skip
from servicecatalog_factory.workflow import tasks_unit_tests_helper


class CreatePortfolioAssociationTaskTest(tasks_unit_tests_helper.FactoryTaskUnitTest):
    region = "region"
    portfolio_name = "portfolio_name"
    description = "description"
    provider_name = "provider_name"
    tags = []
    associations = []
    factory_version = "factory_version"
    create_portfolio_task_ref = "create_portfolio_task_ref"

    def setUp(self) -> None:
        from servicecatalog_factory.workflow.portfolios import (
            create_portfolio_association_task,
        )

        self.module = create_portfolio_association_task

        self.sut = self.module.CreatePortfolioAssociationTask(
            **self.minimal_common_params,
            create_portfolio_task_ref=self.create_portfolio_task_ref,
            region=self.region,
            portfolio_name=self.portfolio_name,
            associations=self.associations,
            factory_version=self.factory_version,
            tags=self.tags,
        )

        self.wire_up_mocks()

    @skip
    def test_requires(self):
        # setup
        # exercise
        actual_result = self.sut.requires()

        # verify
        raise NotImplementedError()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "region": self.region,
            "portfolio_name": self.portfolio_name,
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
