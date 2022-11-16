#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import luigi

from servicecatalog_factory.workflow.tasks import FactoryTask


class CreateTagOptionTask(FactoryTask):
    region = luigi.Parameter()
    tag_option_key = luigi.Parameter()
    tag_option_value = luigi.Parameter()

    def params_for_results_display(self):
        return {
            "region": self.region,
            "tag_option_key": self.tag_option_key,
            "tag_option_value": self.tag_option_value,
        }

    def run(self):
        with self.regional_client("servicecatalog") as servicecatalog:
            try:
                result = servicecatalog.create_tag_option(
                    Key=self.tag_option_key, Value=self.tag_option_value
                ).get("TagOptionDetail")
            except servicecatalog.exceptions.DuplicateResourceException:
                result = servicecatalog.list_tag_options(
                    Filters={
                        "Key": self.tag_option_key,
                        "Value": self.tag_option_value,
                    },
                    PageSize=2,
                ).get("TagOptionDetails")
                assert len(result) == 1
                result = result[0]

            self.write_output(result)
