#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0


def test_bootstrap_stack_name():
    # setup
    from servicecatalog_factory import constants as sut

    expected_result = "servicecatalog-factory"

    # execute
    # verify
    assert sut.BOOTSTRAP_STACK_NAME == expected_result


def test_service_catalog_factory_repo_name():
    # setup
    from servicecatalog_factory import constants as sut

    expected_result = "ServiceCatalogFactory"

    # execute
    # verify
    assert sut.SERVICE_CATALOG_FACTORY_REPO_NAME == expected_result


def test_non_recoverable_states():
    # setup
    from servicecatalog_factory import constants as sut

    expected_result = [
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

    # execute
    # verify
    assert sut.NON_RECOVERABLE_STATES == expected_result


def test_constants():
    # setup
    from servicecatalog_factory import constants as sut

    # execute
    # verify
    assert sut.OUTPUT == "output"
    assert sut.HASH_PREFIX == "a"
    assert sut.CONFIG_PARAM_NAME == "/servicecatalog-factory/config"

    assert sut.BOOTSTRAP_STACK_NAME == "servicecatalog-factory"
    assert sut.BOOTSTRAP_TEMPLATES_STACK_NAME == "servicecatalog-factory-templates"
    assert sut.SERVICE_CATALOG_FACTORY_REPO_NAME == "ServiceCatalogFactory"
    assert sut.NON_RECOVERABLE_STATES == [
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
    assert sut.PRODUCT == "product.j2"
    assert sut.PRODUCT_TERRAFORM == "product-terraform.j2"
    assert sut.PRODUCT_CLOUDFORMATION == "product-cloudformation.j2"
    assert sut.PRODUCT_COMBINED_CLOUDFORMATION == "product-combined-cloudformation.j2"
    assert sut.TERRAFORM_TEMPLATE == "terraform.template.yaml.j2"
    assert sut.ASSOCIATIONS == "associations.j2"

    assert sut.RESULTS_DIRECTORY == "results"

    assert sut.PIPELINE_MODE_COMBINED == "combined"
    assert sut.PIPELINE_MODE_SPILT == "split"
    assert sut.PIPELINE_MODE_DEFAULT == sut.PIPELINE_MODE_SPILT

    assert sut.PROVISIONERS_CLOUDFORMATION == "CloudFormation"
    assert sut.PROVISIONERS_DEFAULT == sut.PROVISIONERS_CLOUDFORMATION

    assert sut.TEMPLATE_FORMATS_YAML == "yaml"
    assert sut.TEMPLATE_FORMATS_DEFAULT == sut.TEMPLATE_FORMATS_YAML

    assert sut.STATUS_ACTIVE == "active"
    assert sut.STATUS_TERMINATED == "terminated"
    assert sut.STATUS_DEFAULT == sut.STATUS_ACTIVE

    assert sut.PACKAGE_BUILD_SPEC_IMAGE_DEFAULT == "aws/codebuild/standard:4.0"

    assert sut.ENVIRONMENT_COMPUTE_TYPE_DEFAULT == "BUILD_GENERAL1_SMALL"
    assert sut.ENVIRONMENT_IMAGE_DEFAULT == "aws/codebuild/standard:4.0"
    assert sut.ENVIRONMENT_TYPE_DEFAULT == "LINUX_CONTAINER"

    assert sut.BUILDSPEC_RUNTIME_VERSIONS_NODEJS_DEFAULT == "12"

    assert sut.DEFAULT_PARTITION == "aws"

    assert sut.CODEPIPELINE_SUPPORTED_REGIONS == [
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
