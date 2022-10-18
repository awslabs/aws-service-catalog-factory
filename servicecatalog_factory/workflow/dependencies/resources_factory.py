#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
from servicecatalog_factory.workflow.dependencies import reservable_resources as r

from servicecatalog_factory.workflow.dependencies import section_names


def create(section_name, parameters_to_use):
    status = parameters_to_use.get("status")

    if section_name == section_names.FOO:
        if status == "terminated":
            resources = []
        else:
            resources = [
                r.CLOUDFORMATION_ENSURE_DELETED_PER_REGION_OF_ACCOUNT,
                r.CLOUDFORMATION_GET_TEMPLATE_SUMMARY_PER_REGION_OF_ACCOUNT,
                r.CLOUDFORMATION_GET_TEMPLATE_PER_REGION_OF_ACCOUNT,
                r.CLOUDFORMATION_CREATE_OR_UPDATE_PER_REGION_OF_ACCOUNT,
            ]

    else:
        raise Exception(f"Unknown section_name: {section_name}")

    result = list()
    for resource in resources:
        try:
            result.append(resource.format(**parameters_to_use))
        except KeyError as e:
            raise Exception(
                f"Failed to inject parameters into resource for '{section_name}': {r} was missing '{e}' in {parameters_to_use}"
            )
    return result
