# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from pytest import fixture
import pkg_resources

@fixture
def sut():
    from servicecatalog_factory import cli
    return cli


def test_version(sut):
    assert sut.VERSION == pkg_resources.require("aws-service-catalog-factory")[0].version


def test_bootstrap_stack_name(sut):
    assert sut.BOOTSTRAP_STACK_NAME == 'servicecatalog-factory'


def test_service_catalog_factory_repo_name(sut):
    assert sut.SERVICE_CATALOG_FACTORY_REPO_NAME == 'ServiceCatalogFactory'
