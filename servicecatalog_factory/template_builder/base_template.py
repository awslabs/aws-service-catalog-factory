# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
SOURCE_OUTPUT_ARTIFACT = "Source"
BUILD_OUTPUT_ARTIFACT = "Build"
VALIDATE_OUTPUT_ARTIFACT = "Validate"
PACKAGE_OUTPUT_ARTIFACT = "Package"
DEPLOY_OUTPUT_ARTIFACT = "Deploy"


class BaseTemplate(object):
    def render(
        self,
        template,
        name,
        version,
        description,
        source,
        product_ids_by_region,
        tags,
        friendly_uid,
    ) -> str:
        return ""
