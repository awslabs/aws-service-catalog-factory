# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import yaml
from nose2.tools import such, params

from unittest import mock as mocker


def fake_version():
    return {
        "Name": "v1",
        "Description": "Lambda and codebuild project needed to run servicecatalog-puppet bootstrap-spoke-as",
        "Active": True,
        "Source": {
            "Provider": "CodeCommit",
            "Configuration": {
                "RepositoryName": "account-vending-account-bootstrap-shared",
                "BranchName": "master",
            },
        },
    }


def fake_component():
    return {
        "Name": "account-vending-account-creation",
        "Owner": "central-it@customer.com",
        "Description": "template used to interact with custom resources in the shared projects",
        "Distributor": "central-it-team",
        "SupportDescription": "Contact us on Chime for help #central-it-team",
        "SupportEmail": "central-it-team@customer.com",
        "SupportUrl": "https://wiki.customer.com/central-it-team/self-service/account-iam",
        "Tags": [{"Key": "product-type", "Value": "iam",}],
        "Versions": [fake_version()],
    }


def fake_portfolio():
    return {
        "DisplayName": "central-it-team-portfolio",
        "Description": "A place for self service products ready for your account",
        "ProviderName": "central-it-team",
        "Associations": ["arn:aws:iam::${AWS::AccountId}:role/Admin",],
        "Tags": [{"Key": "provider"}, {"Value": "central-it-team"},],
        "Components": [fake_component()],
    }


@mocker.patch("os.path.abspath", return_value="some/path/asset.py")
def test_resolve_from_site_packages(abspath_mocked):
    # setup
    from servicecatalog_factory import core as sut

    what = "asset.py"
    site_path = os.path.sep.join(["some", "path"])
    expected_result = os.path.sep.join([site_path, what])

    # execute
    actual_result = sut.resolve_from_site_packages(what)

    # verify
    assert expected_result == actual_result


@mocker.patch("builtins.open")
def test_read_from_site_packages(mocked_open):
    # setup
    from servicecatalog_factory import core as sut

    what = "asset.py"
    expected_result = "foobar"
    mocked_open().read.return_value = expected_result
    mocker.patch.object(sut, "resolve_from_site_packages", return_value="ignored")

    # execute
    actual_result = sut.read_from_site_packages(what)

    # verify
    assert expected_result == actual_result


@mocker.patch("servicecatalog_factory.core.betterboto_client.ClientContextManager")
def test_get_regions(mocked_betterboto_client):
    # setup
    from servicecatalog_factory import core as sut

    expected_result = [
        "us-east-1",
        "us-east-2",
    ]
    mocked_response = {
        "Parameter": {"Value": yaml.safe_dump({"regions": expected_result})}
    }
    mocked_betterboto_client().__enter__().get_parameter.return_value = mocked_response

    # execute
    actual_result = sut.get_regions()

    # verify
    assert actual_result == expected_result


with such.A("get_config") as it:

    @it.should("work")
    @params(
        ({"hello": "world"}, {"foo": "bar"}, {"hello": "world", "foo": "bar"}),
        ({}, {"foo": "bar"}, {"foo": "bar"}),
        ({"hello": "world"}, {}, {"hello": "world"}),
        ({}, {}, {}),
    )
    def test(case, input_one, input_two, expected_results):
        # setup
        from servicecatalog_factory import core as sut

        # exercise
        actual_results = sut.merge(input_one, input_two)

        # verify
        assert expected_results == actual_results

    it.createTests(globals())


@mocker.patch("servicecatalog_factory.core.betterboto_client.ClientContextManager")
def test_get_stacks(mocked_betterboto_client):
    # setup
    from servicecatalog_factory import core as sut

    args = {
        "StackStatusFilter": [
            "CREATE_IN_PROGRESS",
            "CREATE_FAILED",
            "CREATE_COMPLETE",
            "ROLLBACK_IN_PROGRESS",
            "ROLLBACK_FAILED",
            "ROLLBACK_COMPLETE",
            "DELETE_IN_PROGRESS",
            "DELETE_FAILED",
            "UPDATE_IN_PROGRESS",
            "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
            "UPDATE_COMPLETE",
            "UPDATE_ROLLBACK_IN_PROGRESS",
            "UPDATE_ROLLBACK_FAILED",
            "UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS",
            "UPDATE_ROLLBACK_COMPLETE",
            "REVIEW_IN_PROGRESS",
        ]
    }
    expected_result = {"foo": "CREATE_IN_PROGRESS"}
    mocked_betterboto_client().__enter__().list_stacks.return_value = {
        "StackSummaries": [{"StackName": "foo", "StackStatus": "CREATE_IN_PROGRESS"}]
    }

    # execute
    actual_result = sut.get_stacks()

    # verify
    assert actual_result == expected_result
    mocked_betterboto_client().__enter__().list_stacks.assert_called_with(**args)


@mocker.patch("servicecatalog_factory.core.betterboto_client.ClientContextManager")
def test_get_stacks_if_empty(mocked_betterboto_client):
    # setup
    from servicecatalog_factory import core as sut

    args = {
        "StackStatusFilter": [
            "CREATE_IN_PROGRESS",
            "CREATE_FAILED",
            "CREATE_COMPLETE",
            "ROLLBACK_IN_PROGRESS",
            "ROLLBACK_FAILED",
            "ROLLBACK_COMPLETE",
            "DELETE_IN_PROGRESS",
            "DELETE_FAILED",
            "UPDATE_IN_PROGRESS",
            "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
            "UPDATE_COMPLETE",
            "UPDATE_ROLLBACK_IN_PROGRESS",
            "UPDATE_ROLLBACK_FAILED",
            "UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS",
            "UPDATE_ROLLBACK_COMPLETE",
            "REVIEW_IN_PROGRESS",
        ]
    }
    expected_result = {}
    mocked_betterboto_client().__enter__().list_stacks.return_value = {
        "StackSummaries": []
    }

    # execute
    actual_result = sut.get_stacks()

    # verify
    assert actual_result == expected_result
    mocked_betterboto_client().__enter__().list_stacks.assert_called_with(**args)


@mocker.patch("servicecatalog_factory.core.bootstrap")
def test_bootstrap_branch(bootstrap_mocked):
    # setup
    from servicecatalog_factory import core as sut

    branch_name = "foo"
    (
        branch_to_bootstrap,
        source_provider,
        owner,
        repo,
        branch,
        poll_for_source_changes,
        webhook_secret,
        scm_connection_arn,
        scm_full_repository_id,
        scm_branch_name,
        scm_bucket_name,
        scm_object_key,
        create_repo,
    ) = (
        branch_name,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )
    # exercise
    sut.bootstrap_branch(
        branch_to_bootstrap,
        source_provider,
        owner,
        repo,
        branch,
        poll_for_source_changes,
        webhook_secret,
        scm_connection_arn,
        scm_full_repository_id,
        scm_branch_name,
        scm_bucket_name,
        scm_object_key,
        create_repo,
    )

    # verify
    assert (
        sut.constants.VERSION
        == "https://github.com/awslabs/aws-service-catalog-factory/archive/{}.zip".format(
            branch_name
        )
    )
    bootstrap_mocked.assert_called_once()
