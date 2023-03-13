#  Copyright 2023 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from servicecatalog_factory.workflow.tasks import FactoryTask


class AssociationProductsTasks(FactoryTask):
    def run(self):
        self.write_output_raw("{}")
