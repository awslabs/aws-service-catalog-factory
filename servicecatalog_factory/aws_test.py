# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest
from pytest import fixture


@fixture
def sut():
    from servicecatalog_factory import aws
    return aws


def test_get_bucket_name_if_not_exists(mocker, sut):
    # setup
    expected_result = 'Could not find bucket'
    mocked_betterboto_client = mocker.patch.object(sut.betterboto_client, 'ClientContextManager')
    mocked_response = {
        'Stacks': [{
            "Outputs": [{"OutputKey": "BucketName", "OutputValue": expected_result}]
        }]
    }
    mocked_betterboto_client().__enter__().describe_stacks.return_value = mocked_response

    # execute
    with pytest.raises(Exception) as excinfo:
        sut.get_bucket_name()

    # verify
    assert str(excinfo.value) == expected_result
    mocked_betterboto_client().__enter__().describe_stacks.assert_called_with(
        StackName=sut.constants.BOOTSTRAP_STACK_NAME)


def test_get_bucket_name_stack_length_more(mocker, sut):
    # setup
    expected_result = 'There should only be one stack with the name'
    mocked_betterboto_client = mocker.patch.object(sut.betterboto_client, 'ClientContextManager')
    mocked_response = {
        'Stacks': [{
            "Outputs": [{"OutputKey": "CatalogBucketName", "OutputValue": expected_result}]
        },
            {
                "Outputs": [{"OutputKey": "CatalogBucketName", "OutputValue": 'hello'}]
            }]
    }
    mocked_betterboto_client().__enter__().describe_stacks.return_value = mocked_response

    # execute
    with pytest.raises(Exception) as excinfo:
        sut.get_bucket_name()

    # verify
    assert str(excinfo.value) == expected_result
    mocked_betterboto_client().__enter__().describe_stacks.assert_called_with(
        StackName=sut.constants.BOOTSTRAP_STACK_NAME)


def test_get_bucket_name(mocker, sut):
    # setup
    expected_result = 'test-bucket'
    mocked_betterboto_client = mocker.patch.object(sut.betterboto_client, 'ClientContextManager')
    mocked_response = {
        'Stacks': [{
            "Outputs": [{"OutputKey": "CatalogBucketName", "OutputValue": expected_result}]
        }]
    }
    mocked_betterboto_client().__enter__().describe_stacks.return_value = mocked_response

    # execute
    actual_result = sut.get_bucket_name()

    # verify
    assert actual_result == expected_result
    mocked_betterboto_client().__enter__().describe_stacks.assert_called_with(
        StackName=sut.constants.BOOTSTRAP_STACK_NAME)
