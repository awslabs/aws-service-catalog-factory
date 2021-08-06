#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import luigi

from servicecatalog_factory import constants
from servicecatalog_factory.workflow.tasks import FactoryTask


class GetBucketTask(FactoryTask):
    region = luigi.Parameter(default=constants.HOME_REGION)

    def params_for_results_display(self):
        return {
            "region": self.region,
        }

    def run(self):
        s3_bucket_url = None
        with self.regional_client("cloudformation") as cloudformation:
            response = cloudformation.describe_stacks(
                StackName=constants.BOOTSTRAP_STACK_NAME
            )
            assert (
                len(response.get("Stacks")) == 1
            ), "There should only be one stack with the name"
            outputs = response.get("Stacks")[0].get("Outputs")
            for output in outputs:
                if output.get("OutputKey") == "CatalogBucketName":
                    s3_bucket_url = output.get("OutputValue")
            assert s3_bucket_url is not None, "Could not find bucket"
            self.write_output({"s3_bucket_url": s3_bucket_url})
