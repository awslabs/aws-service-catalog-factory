#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from unittest import skip
from servicecatalog_factory.workflow import tasks_unit_tests_helper


class CreateProductTaskTest(tasks_unit_tests_helper.FactoryTaskUnitTest):
    uid = "uid"
    region = "region"
    name = "name"
    owner = "owner"
    description = "description"
    distributor = "distributor"
    support_description = "support_description"
    support_email = "support_email"
    support_url = "support_url"
    tags = []

    def setUp(self) -> None:
        from servicecatalog_factory.workflow.portfolios import create_product_task

        self.module = create_product_task

        self.sut = self.module.CreateProductTask(
            uid=self.uid,
            region=self.region,
            name=self.name,
            owner=self.owner,
            description=self.description,
            distributor=self.distributor,
            support_description=self.support_description,
            support_email=self.support_email,
            support_url=self.support_url,
            tags=self.tags,
        )

        self.wire_up_mocks()

    def test_params_for_results_display(self):
        # setup
        expected_result = {
            "region": self.region,
            "uid": self.uid,
            "name": self.name,
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
