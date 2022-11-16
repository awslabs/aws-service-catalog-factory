#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os

import pkg_resources

OUTPUT = "output"
HASH_PREFIX = "a"
CONFIG_PARAM_NAME = "/servicecatalog-factory/config"

PUBLISHED_VERSION = pkg_resources.require("aws-service-catalog-factory")[0].version
VERSION = os.getenv("SCF_VERSION_OVERRIDE", PUBLISHED_VERSION)

BOOTSTRAP_STACK_NAME = "servicecatalog-factory"
BOOTSTRAP_TEMPLATES_STACK_NAME = "servicecatalog-factory-templates"
SERVICE_CATALOG_FACTORY_REPO_NAME = "ServiceCatalogFactory"
NON_RECOVERABLE_STATES = [
    "ROLLBACK_COMPLETE",
    "CREATE_IN_PROGRESS",
    "ROLLBACK_IN_PROGRESS",
    "DELETE_IN_PROGRESS",
    "UPDATE_IN_PROGRESS",
    "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
    "UPDATE_ROLLBACK_IN_PROGRESS",
    "UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS",
    "REVIEW_IN_PROGRESS",
]
PRODUCT = "product.j2"
PRODUCT_TERRAFORM = "product-terraform.j2"
TERRAFORM_TEMPLATE = "terraform.template.yaml.j2"
ASSOCIATIONS = "associations.j2"
HOME_REGION = os.environ.get(
    "AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "eu-west-1")
)

RESULTS_DIRECTORY = "results"

PIPELINE_MODE_COMBINED = "combined"
PIPELINE_MODE_SPILT = "split"
PIPELINE_MODE_DEFAULT = PIPELINE_MODE_SPILT

PROVISIONERS_CLOUDFORMATION = "CloudFormation"
PROVISIONERS_DEFAULT = PROVISIONERS_CLOUDFORMATION

TEMPLATE_FORMATS_YAML = "yaml"
TEMPLATE_FORMATS_DEFAULT = TEMPLATE_FORMATS_YAML

STATUS_ACTIVE = "active"
STATUS_TERMINATED = "terminated"
STATUS_DEFAULT = STATUS_ACTIVE

PACKAGE_BUILD_SPEC_IMAGE_DEFAULT = "aws/codebuild/standard:4.0"

PACKAGE_BUILD_SPEC_DEFAULT = """
      version: 0.2
      phases:
        install:
          runtime-versions:
            python: 3.7
        build:
          commands:
            - cd $SOURCE_PATH
          {% for region in ALL_REGIONS %}
            - aws cloudformation package --region {{ region }} --template $(pwd)/product.template.yaml --s3-bucket sc-factory-artifacts-${ACCOUNT_ID}-{{ region }} --s3-prefix ${STACK_NAME} --output-template-file product.template-{{ region }}.yaml
          {% endfor %}
      artifacts:
        files:
          - '*'
          - '**/*'
"""

ENVIRONMENT_COMPUTE_TYPE_DEFAULT = "BUILD_GENERAL1_SMALL"
ENVIRONMENT_IMAGE_DEFAULT = "aws/codebuild/standard:4.0"
BUILD_STAGE_TIMEOUT_IN_MINUTES_DEFAULT = 60
ENVIRONMENT_TYPE_DEFAULT = "LINUX_CONTAINER"

BUILDSPEC_RUNTIME_VERSIONS_NODEJS_DEFAULT = "12"

DEFAULT_PARTITION = "aws"
PARTITION = os.getenv("PARTITION", DEFAULT_PARTITION)

CODEPIPELINE_SUPPORTED_REGIONS = [
    "us-east-2",
    "us-east-1",
    "us-west-1",
    "us-west-2",
    "ap-east-1",
    "ap-south-1",
    "ap-northeast-2",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-northeast-1",
    "ca-central-1",
    "eu-central-1",
    "eu-west-1",
    "eu-west-2",
    "eu-south-1",
    "eu-west-3",
    "eu-north-1",
    "sa-east-1",
    "us-gov-west-1",
]

STATIC_HTML_PAGE = "static-html-page.html"

GENERIC_BUILD_PROJECT_PRIVILEGED_MODE_DEFAULT = False

INITIALISER_STACK_NAME_SSM_PARAMETER = "service-catalog-factory-initialiser-stack-name"


CONFIG_SHOULD_PIPELINES_INHERIT_TAGS = "should_pipelines_inherit_tags"


SERVICE_CATALOG_FACTORY_PIPELINES = "/servicecatalog-factory/pipelines"

BOOTSTRAP_TYPE_SECONDARY = "SECONDARY"
BOOTSTRAP_TYPE_PRIMARY = "PRIMARY"

BOOTSTRAP_SECONDARY_TEMPLATE_NAME = "servicecatalog-factory-secondary"


FACTORY_LOGGER_NAME = "factory-logger"
FACTORY_SCHEDULER_LOGGER_NAME = "factory-logger-scheduler"

AWS_URL_SUFFIX_DEFAULT = "amazonaws.com"
