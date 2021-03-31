# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0


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
