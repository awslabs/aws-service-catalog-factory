#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

PER_REGION = "_{region}"
PER_REGION_OF_ACCOUNT = PER_REGION + "_OF_{account_id}"

CLOUDFORMATION_ENSURE_DELETED_PER_REGION_OF_ACCOUNT = (
    "CLOUDFORMATION_ENSURE_DELETED" + PER_REGION_OF_ACCOUNT
)
CLOUDFORMATION_GET_TEMPLATE_SUMMARY_PER_REGION_OF_ACCOUNT = (
    "CLOUDFORMATION_GET_TEMPLATE_SUMMARY" + PER_REGION_OF_ACCOUNT
)
CLOUDFORMATION_GET_TEMPLATE_PER_REGION_OF_ACCOUNT = (
    "CLOUDFORMATION_GET_TEMPLATE" + PER_REGION_OF_ACCOUNT
)
CLOUDFORMATION_CREATE_OR_UPDATE_PER_REGION_OF_ACCOUNT = (
    "CLOUDFORMATION_CREATE_OR_UPDATE" + PER_REGION_OF_ACCOUNT
)
CLOUDFORMATION_LIST_STACKS_PER_REGION_OF_ACCOUNT = (
    "CLOUDFORMATION_LIST_STACKS" + PER_REGION_OF_ACCOUNT
)
CLOUDFORMATION_DESCRIBE_STACKS_PER_REGION_OF_ACCOUNT = (
    "CLOUDFORMATION_DESCRIBE_STACKS" + PER_REGION_OF_ACCOUNT
)

SERVICE_CATALOG_SCAN_PROVISIONED_PRODUCTS_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_SCAN_PROVISIONED_PRODUCTS" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_DESCRIBE_PROVISIONED_PRODUCT_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_DESCRIBE_PROVISIONED_PRODUCT" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_UPDATE_PROVISIONED_PRODUCT_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_UPDATE_PROVISIONED_PRODUCT" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_PROVISION_PRODUCT_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_PROVISION_PRODUCT" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_TERMINATE_PROVISIONED_PRODUCT_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_TERMINATE_PROVISIONED_PRODUCT" + PER_REGION_OF_ACCOUNT
)

SERVICE_CATALOG_TERMINATE_PROVISIONED_PRODUCT_PLAN_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_TERMINATE_PROVISIONED_PRODUCT_PLAN" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_CREATE_PROVISIONED_PRODUCT_PLAN_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_CREATE_PROVISIONED_PRODUCT_PLAN" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_DESCRIBE_PROVISIONED_PRODUCT_PLAN_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_DESCRIBE_PROVISIONED_PRODUCT_PLAN" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_EXECUTE_PROVISIONED_PRODUCT_PLAN_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_EXECUTE_PROVISIONED_PRODUCT_PLAN" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_DESCRIBE_RECORD_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_DESCRIBE_RECORD" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_LIST_PROVISIONED_PRODUCT_PLANS_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_LIST_PROVISIONED_PRODUCT_PLANS" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_LIST_LAUNCH_PATHS_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_LIST_LAUNCH_PATHS" + PER_REGION_OF_ACCOUNT
)

SERVICE_CATALOG_LIST_PRINCIPALS_FOR_PORTFOLIO_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_LIST_PRINCIPALS_FOR_PORTFOLIO" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_DISASSOCIATE_PRINCIPAL_FROM_PORTFOLIO_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_DISASSOCIATE_PRINCIPAL_FROM_PORTFOLIO" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_ASSOCIATE_PRINCIPAL_FROM_PORTFOLIO_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_ASSOCIATE_PRINCIPAL_FROM_PORTFOLIO" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_LIST_PORTFOLIOS_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_LIST_PORTFOLIOS" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_DELETE_PORTFOLIOS_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_DELETE_PORTFOLIOS" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_CREATE_PORTFOLIOS_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_CREATE_PORTFOLIOS" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_LIST_ACCEPTED_PORTFOLIO_SHARES_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_LIST_ACCEPTED_PORTFOLIO_SHARES" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_LIST_PORTFOLIO_ACCESS_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_LIST_PORTFOLIO_ACCESS" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_CREATE_PORTFOLIO_SHARE = "SERVICE_CATALOG_CREATE_PORTFOLIO_SHARE"
SERVICE_CATALOG_CREATE_PORTFOLIO_SHARE_PER_REGION = (
    "SERVICE_CATALOG_CREATE_PORTFOLIO_SHARE" + PER_REGION
)
SERVICE_CATALOG_CREATE_PORTFOLIO_SHARE_PER_REGION = (
    "SERVICE_CATALOG_CREATE_PORTFOLIO_SHARE" + PER_REGION
)
SERVICE_CATALOG_DESCRIBE_PORTFOLIO_SHARE_STATUS_PER_REGION = (
    "SERVICE_CATALOG_DESCRIBE_PORTFOLIO_SHARE_STATUS" + PER_REGION
)
SERVICE_CATALOG_CREATE_PORTFOLIO_SHARE_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_CREATE_PORTFOLIO_SHARE" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_ACCEPT_PORTFOLIO_SHARE_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_ACCEPT_PORTFOLIO_SHARE" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_SEARCH_PRODUCTS_AS_ADMIN_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_SEARCH_PRODUCTS_AS_ADMIN" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_DESCRIBE_PRODUCT_AS_ADMIN_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_DESCRIBE_PRODUCT_AS_ADMIN" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_DESCRIBE_PROVISIONING_PARAMETERS_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_DESCRIBE_PROVISIONING_PARAMETERS" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_LIST_PROVISIONING_ARTIFACTS_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_LIST_PROVISIONING_ARTIFACTS" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_COPY_PRODUCT_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_COPY_PRODUCT" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_DESCRIBE_COPY_PRODUCT_STATUS_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_DESCRIBE_COPY_PRODUCT_STATUS" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_ASSOCIATE_PRODUCT_WITH_PORTFOLIO_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_ASSOCIATE_PRODUCT_WITH_PORTFOLIO" + PER_REGION_OF_ACCOUNT
)
SERVICE_CATALOG_UPDATE_PROVISIONING_ARTIFACT_PER_REGION_OF_ACCOUNT = (
    "SERVICE_CATALOG_UPDATE_PROVISIONING_ARTIFACT" + PER_REGION_OF_ACCOUNT
)

SSM_GET_PARAMETER_PER_REGION_OF_ACCOUNT = "SSM_GET_PARAMETER" + PER_REGION_OF_ACCOUNT
SSM_DELETE_PARAMETER_PER_REGION_OF_ACCOUNT = (
    "SSM_DELETE_PARAMETER" + PER_REGION_OF_ACCOUNT
)
SSM_PUT_PARAMETER_PER_REGION_OF_ACCOUNT = "SSM_PUT_PARAMETER" + PER_REGION_OF_ACCOUNT
SSM_GET_PARAMETER_BY_PATH_PER_REGION_OF_ACCOUNT = (
    "SSM_GET_PARAMETER_BY_PATH" + PER_REGION_OF_ACCOUNT
)


ORGANIZATIONS_ATTACH_POLICY_PER_REGION = "ORGANIZATIONS_ATTACH_POLICY" + PER_REGION
ORGANIZATIONS_DETACH_POLICY_PER_REGION = "ORGANIZATIONS_DETACH_POLICY" + PER_REGION
ORGANIZATIONS_LIST_POLICIES_PER_REGION = "ORGANIZATIONS_LIST_POLICIES" + PER_REGION
ORGANIZATIONS_CREATE_POLICIES_PER_REGION = "ORGANIZATIONS_CREATE_POLICIES" + PER_REGION
ORGANIZATIONS_DESCRIBE_POLICIES_PER_REGION = (
    "ORGANIZATIONS_DESCRIBE_POLICIES" + PER_REGION
)
ORGANIZATIONS_UPDATE_POLICIES_PER_REGION = "ORGANIZATIONS_UPDATE_POLICIES" + PER_REGION

IAM_SIMULATE_POLICY_PER_REGION_OF_ACCOUNT = (
    "IAM_SIMULATE_POLICY_{simulation_type}" + PER_REGION_OF_ACCOUNT
)

LAMBDA_INVOKE_PER_REGION_OF_ACCOUNT = "LAMBDA_INVOKE" + PER_REGION_OF_ACCOUNT

CODEBUILD_START_BUILD_PER_REGION_OF_ACCOUNT = (
    "CODEBUILD_START_BUILD" + PER_REGION_OF_ACCOUNT
)
CODEBUILD_BATCH_GET_PROJECTS_PER_REGION_OF_ACCOUNT = (
    "CODEBUILD_BATCH_GET_PROJECTS_{project_name}" + PER_REGION_OF_ACCOUNT
)

CAN_ONLY_BE_RUN_ONCE_AT_A_TIME = "CAN_ONLY_BE_RUN_ONCE_AT_A_TIME"
