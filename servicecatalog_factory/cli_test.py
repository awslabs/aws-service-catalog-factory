# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from pytest import fixture
import pkg_resources
import os

@fixture
def sut():
    from servicecatalog_factory import cli
    return cli


def test_version(sut):
    # setup
    # execute
    # verify
    assert sut.VERSION == pkg_resources.require("aws-service-catalog-factory")[0].version


def test_bootstrap_stack_name(sut):
    # setup
    # execute
    # verify
    assert sut.BOOTSTRAP_STACK_NAME == 'servicecatalog-factory'


def test_service_catalog_factory_repo_name(sut):
    # setup
    # execute
    # verify
    assert sut.SERVICE_CATALOG_FACTORY_REPO_NAME == 'ServiceCatalogFactory'


def test_resolve_from_site_packages(mocker, sut):
    # setup
    what = 'asset.py'
    site_path = os.path.sep.join(['some','path'])
    abspath = os.path.sep.join([site_path, 'cli.py'])
    expected_result = os.path.sep.join([site_path, what])
    mocker.patch.object(os.path, 'abspath', return_value=abspath)

    # execute
    actual_result = sut.resolve_from_site_packages(what)

    # verify
    assert expected_result == actual_result


def test_read_from_site_packages(mocker, sut):
    # setup
    what = 'asset.py'
    expected_result = 'foobar'
    mocked_open = mocker.patch('builtins.open')
    mocked_open().read.return_value = expected_result
    mocker.patch.object(sut, 'resolve_from_site_packages', return_value='ignored')

    # execute
    actual_result = sut.read_from_site_packages(what)

    # verify
    assert expected_result == actual_result
