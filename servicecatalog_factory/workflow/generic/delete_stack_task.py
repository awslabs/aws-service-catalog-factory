#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
from servicecatalog_factory.workflow.tasks import FactoryTask
import luigi


class DeleteStackTask(FactoryTask):
    region = luigi.Parameter()
    stack_name = luigi.Parameter()

    def run(self):
        with self.regional_client("cloudformation") as cloudformation:
            cloudformation.ensure_deleted(StackName=self.stack_name)

        self.write_output_raw("{}")
