#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from servicecatalog_factory.workflow.dependencies import section_names
from servicecatalog_factory.workflow.dependencies import reservable_resources as r


def create(section_name, parameters_to_use):
    status = parameters_to_use.get("status")

    if section_name == section_names.GET_BUCKET:
        if status == "terminated":
            resources = []
        else:
            resources = [r.CLOUDFORMATION_DESCRIBE_STACKS_PER_REGION_OF_ACCOUNT]

    elif section_name == section_names.CREATE_PRODUCT_TASK:
        if status == "terminated":
            resources = []
        else:
            resources = [
                r.SERVICE_CATALOG_SEARCH_PRODUCTS_AS_ADMIN_PER_REGION_OF_ACCOUNT,
                r.SERVICE_CATALOG_UPDATE_PRODUCT_PER_REGION_OF_ACCOUNT,
                r.SERVICE_CATALOG_CREATE_PRODUCT_PER_REGION_OF_ACCOUNT,
            ]

    elif section_name == section_names.CREATE_PORTFOLIO_TASK:
        if status == "terminated":
            resources = []
        else:
            resources = [
                r.SERVICE_CATALOG_LIST_PORTFOLIOS_PER_REGION_OF_ACCOUNT,
                r.SERVICE_CATALOG_CREATE_PORTFOLIO_PER_REGION_OF_ACCOUNT,
            ]

    elif section_name == section_names.CREATE_GENERIC_COMBINED_PIPELINE_TASK:
        if status == "terminated":
            resources = []
        else:
            resources = [
                r.CLOUDFORMATION_CREATE_OR_UPDATE_PER_REGION_OF_ACCOUNT,
            ]

    elif section_name == section_names.CREATE_PORTFOLIO_ASSOCIATIONS_TASK:
        if status == "terminated":
            resources = []
        else:
            resources = [
                r.CLOUDFORMATION_CREATE_OR_UPDATE_PER_REGION_OF_ACCOUNT,
            ]

    elif section_name == section_names.CREATE_PRODUCT_ASSOCIATION_TASK:
        if status == "terminated":
            resources = []
        else:
            resources = [
                r.SERVICE_CATALOG_LIST_PORTFOLIOS_PER_REGION_OF_ACCOUNT,
                r.SERVICE_CATALOG_ASSOCIATE_PRODUCT_WITH_PORTFOLIO_PER_REGION_OF_ACCOUNT,
            ]

    elif section_name == section_names.CREATE_LAUNCH_ROLE_NAME_CONSTRAINTS_TASK:
        if status == "terminated":
            resources = []
        else:
            resources = [
                r.CLOUDFORMATION_CREATE_OR_UPDATE_PER_REGION_OF_ACCOUNT,
            ]

    elif section_name == section_names.ENSURE_PRODUCT_VERSION_DETAILS_CORRECT_TASK:
        if status == "terminated":
            resources = []
        else:
            resources = [
                r.SERVICE_CATALOG_LIST_PROVISIONING_ARTIFACTS_PER_REGION_OF_ACCOUNT,
                r.SERVICE_CATALOG_UPDATE_PROVISIONING_ARTIFACT_PER_REGION_OF_ACCOUNT,
            ]

    elif section_name == section_names.CREATE_CODE_REPO_TASK:
        if status == "terminated":
            resources = []
        else:
            resources = [
                r.CODECOMMIT_GET_REPOSITORY_PER_REGION_OF_ACCOUNT,
                r.CODECOMMIT_CREATE_REPOSITORY_PER_REGION_OF_ACCOUNT,
                r.CODECOMMIT_GET_BRANCH_PER_REGION_OF_ACCOUNT,
                r.CODECOMMIT_CREATE_BRANCH_PER_REGION_OF_ACCOUNT,
                r.CODECOMMIT_CREATE_COMMIT_PER_REGION_OF_ACCOUNT,
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
