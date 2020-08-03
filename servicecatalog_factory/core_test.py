# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import hashlib

import pytest
from pytest import fixture
import pkg_resources
import os
import yaml


@fixture
def mocked_open(mocker):
    return mocker.patch("builtins.open")


@fixture
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


@fixture
def fake_component(fake_version):
    return {
        "Name": "account-vending-account-creation",
        "Owner": "central-it@customer.com",
        "Description": "template used to interact with custom resources in the shared projects",
        "Distributor": "central-it-team",
        "SupportDescription": "Contact us on Chime for help #central-it-team",
        "SupportEmail": "central-it-team@customer.com",
        "SupportUrl": "https://wiki.customer.com/central-it-team/self-service/account-iam",
        "Tags": [{"Key": "product-type", "Value": "iam",}],
        "Versions": [fake_version],
    }


@fixture
def fake_portfolio(fake_component):
    return {
        "DisplayName": "central-it-team-portfolio",
        "Description": "A place for self service products ready for your account",
        "ProviderName": "central-it-team",
        "Associations": ["arn:aws:iam::${AWS::AccountId}:role/Admin",],
        "Tags": [{"Key": "provider"}, {"Value": "central-it-team"},],
        "Components": [fake_component],
    }


@fixture
def sut():
    from servicecatalog_factory import core

    return core


def test_version(sut):
    # setup
    expected_result = pkg_resources.require("aws-service-catalog-factory")[0].version

    # execute
    # verify
    assert sut.VERSION == expected_result


def test_resolve_from_site_packages(mocker, sut):
    # setup
    what = "asset.py"
    site_path = os.path.sep.join(["some", "path"])
    abspath = os.path.sep.join([site_path, "cli.py"])
    expected_result = os.path.sep.join([site_path, what])
    mocker.patch.object(os.path, "abspath", return_value=abspath)

    # execute
    actual_result = sut.resolve_from_site_packages(what)

    # verify
    assert expected_result == actual_result


def test_read_from_site_packages(mocker, sut, mocked_open):
    # setup
    what = "asset.py"
    expected_result = "foobar"
    mocked_open().read.return_value = expected_result
    mocker.patch.object(sut, "resolve_from_site_packages", return_value="ignored")

    # execute
    actual_result = sut.read_from_site_packages(what)

    # verify
    assert expected_result == actual_result


def test_get_regions(mocker, sut):
    # setup
    expected_result = [
        "us-east-1",
        "us-east-2",
    ]
    mocked_betterboto_client = mocker.patch.object(
        sut.betterboto_client, "ClientContextManager"
    )
    mocked_response = {
        "Parameter": {"Value": yaml.safe_dump({"regions": expected_result})}
    }
    mocked_betterboto_client().__enter__().get_parameter.return_value = mocked_response

    # execute
    actual_result = sut.get_regions()

    # verify
    assert actual_result == expected_result


@pytest.mark.parametrize(
    "input_one, input_two, expected_results",
    [
        ({"hello": "world"}, {"foo": "bar"}, {"hello": "world", "foo": "bar"}),
        ({}, {"foo": "bar"}, {"foo": "bar"}),
        ({"hello": "world"}, {}, {"hello": "world"}),
        ({}, {}, {}),
    ],
)
def test_merge_case(input_one, input_two, expected_results, sut):
    # setup
    # exercise
    actual_results = sut.merge(input_one, input_two)

    # verify
    assert expected_results == actual_results


def test_get_stacks(mocker, sut):
    # setup
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
    mocked_betterboto_client = mocker.patch.object(
        sut.betterboto_client, "ClientContextManager"
    )
    mocked_betterboto_client().__enter__().list_stacks.return_value = {
        "StackSummaries": [{"StackName": "foo", "StackStatus": "CREATE_IN_PROGRESS"}]
    }

    # execute
    actual_result = sut.get_stacks()

    # verify
    assert actual_result == expected_result
    mocked_betterboto_client().__enter__().list_stacks.assert_called_with(**args)


def test_get_stacks_if_empty(mocker, sut):
    # setup
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
    mocked_betterboto_client = mocker.patch.object(
        sut.betterboto_client, "ClientContextManager"
    )
    mocked_betterboto_client().__enter__().list_stacks.return_value = {
        "StackSummaries": []
    }

    # execute
    actual_result = sut.get_stacks()

    # verify
    assert actual_result == expected_result
    mocked_betterboto_client().__enter__().list_stacks.assert_called_with(**args)


def test_deploy(mocker, sut, fake_portfolio, fake_component, fake_version):
    # setup
    path = "some_path"
    mocked_files = [
        "file1.yaml",
        "file2.yaml",
    ]

    mocked_portfolios = {"Portfolios": [fake_portfolio]}
    expected_portfolios_generated = [
        os.path.sep.join([path, mocked_files[0]]),
        os.path.sep.join([path, mocked_files[1]]),
    ]
    mocked_get_stacks = mocker.patch.object(sut, "get_stacks")
    # mock_stacks = "hello world"
    # mocked_get_stacks.return_value = mock_stacks
    mocked_listdir = mocker.patch.object(os, "listdir")
    mocked_generate_portfolios = mocker.patch.object(sut, "generate_portfolios")
    mocked_run_deploy_for_component = mocker.patch.object(
        sut, "run_deploy_for_component"
    )
    # mocked_run_deploy_for_component_groups = mocker.patch.object(sut, 'run_deploy_for_component_groups')
    mocked_generate_portfolios.return_value = mocked_portfolios
    mocked_listdir.return_value = mocked_files

    # execute
    sut.deploy(path)

    # verify
    mocked_get_stacks.assert_called_once()
    mocked_listdir.assert_called_once_with(path)
    mocked_generate_portfolios.assert_any_call(expected_portfolios_generated[0])
    mocked_generate_portfolios.assert_any_call(expected_portfolios_generated[1])
    mocked_run_deploy_for_component.assert_any_call(
        "output/file1",
        "file1-central-it-team-portfolio-account-vending-account-creation-v1",
    )
    mocked_run_deploy_for_component.assert_any_call(
        "output/file2",
        "file2-central-it-team-portfolio-account-vending-account-creation-v1",
    )


def test_get_hash_for_template(mocker, sut):
    # setup
    mock_md5 = mocker.patch.object(hashlib, "md5")
    fake_hash = "fubar"
    mock_md5().hexdigest.return_value = fake_hash
    expected_result = f"{sut.constants.HASH_PREFIX}{fake_hash}"
    template = "foo"

    # exercise
    actual_result = sut.get_hash_for_template(template)

    # verify
    mock_md5.assert_called()
    mock_md5().update.assert_called_with(str.encode(template))
    assert expected_result == actual_result


def test_run_deploy_for_component(mocker, sut, mocked_open):
    # setup
    path = "some/path"
    friendly_uid = "some/uid"
    fake_template = "foo"
    mocked_client_context_manager = mocker.patch.object(
        sut.betterboto_client, "ClientContextManager"
    )
    mocked_open().__enter__().read.return_value = fake_template

    # exercise
    sut.run_deploy_for_component(path, friendly_uid)

    # verify
    mocked_open.assert_called_with(
        os.path.sep.join([path, "{}.template.yaml".format(friendly_uid)])
    )
    mocked_client_context_manager().__enter__().create_or_update.assert_called_once_with(
        StackName=friendly_uid, TemplateBody=fake_template,
    )


@pytest.mark.skip
def test_nuke_product_version():
    pass


@pytest.mark.skip
def test_nuke_stack():
    pass


@pytest.mark.skip
def test_bootstrap_branch():
    pass


def test_bootstrap_branch(mocker, sut):
    # setup
    branch_name = "foo"
    mocked_bootstrap = mocker.patch.object(sut, "bootstrap")
    # exercise
    sut.bootstrap_branch(branch_name)

    # verify
    assert (
        sut.constants.VERSION
        == "https://github.com/awslabs/aws-service-catalog-factory/archive/{}.zip".format(
            branch_name
        )
    )
    mocked_bootstrap.assert_called_once()


@pytest.mark.skip
def test_bootstrap():
    pass


@pytest.mark.skip
def test_bootstrap():
    pass


@pytest.mark.skip
def test_seed():
    pass


@pytest.mark.skip
def test_seed():
    pass


@pytest.mark.skip
def test_version():
    pass


@pytest.mark.skip
def test_version():
    pass


@pytest.mark.skip
def test_upload_config():
    pass


@pytest.mark.skip
def test_upload_config():
    pass


@pytest.mark.skip
def test_fix_issues():
    pass


@pytest.mark.skip
def test_fix_issues():
    pass


@pytest.mark.skip
def test_fix_issues_for_portfolio():
    pass


@pytest.mark.skip
def test_delete_stack_from_all_regions():
    pass


@pytest.mark.skip
def test_delete_stack_from_all_regions():
    pass


@pytest.mark.skip
def test_delete_stack_from_all_regions():
    pass


@pytest.mark.skip
def test_delete_stack_from_a_regions():
    pass


@pytest.mark.skip
def test_quick_start():
    pass


@pytest.mark.skip
def test_do_test_quick_start():
    pass


@pytest.mark.skip
def test_add_or_update_file_in_branch_for_repo():
    pass


@pytest.mark.skip
def test_wait_for_pipeline():
    pass
