# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest
from pytest import fixture
import pkg_resources
import os
import yaml


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


def test_non_recoverable_states(sut):
    # setup
    # execute
    # verify
    assert sut.NON_RECOVERABLE_STATES == [
        "ROLLBACK_COMPLETE",
        'CREATE_IN_PROGRESS',
        'ROLLBACK_IN_PROGRESS',
        'DELETE_IN_PROGRESS',
        'UPDATE_IN_PROGRESS',
        'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS',
        'UPDATE_ROLLBACK_IN_PROGRESS',
        'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS',
        'REVIEW_IN_PROGRESS',
    ]


def test_resolve_from_site_packages(mocker, sut):
    # setup
    what = 'asset.py'
    site_path = os.path.sep.join(['some', 'path'])
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


def test_get_regions(mocker, sut):
    # setup
    expected_result = [
        'us-east-1',
        'us-east-2',
    ]
    mocked_betterboto_client = mocker.patch.object(sut.betterboto_client, 'ClientContextManager')
    mocked_response = {
        'Parameter': {
            "Value": yaml.safe_dump({'regions': expected_result})
        }
    }
    mocked_betterboto_client().__enter__().get_parameter.return_value = mocked_response

    # execute
    actual_result = sut.get_regions()

    # verify
    assert actual_result == expected_result


def test_find_portfolio(mocker, sut):
    # setup
    portfolio_searching_for = 'foo'

    expected_response = {'DisplayName': portfolio_searching_for}
    mock_service_catalog = mocker.Mock()
    mock_service_catalog.list_portfolios_single_page.return_value = {
        'PortfolioDetails': [
            {
                'DisplayName': "Not{}".format(portfolio_searching_for)
            },
            expected_response
        ]
    }

    # exercise
    actual_response = sut.find_portfolio(mock_service_catalog, portfolio_searching_for)

    # verify
    assert expected_response == actual_response


def test_find_portfolio_non_matching(mocker, sut):
    # setup
    portfolio_searching_for = 'foo'

    expected_response = {}
    mock_service_catalog = mocker.Mock()
    mock_service_catalog.list_portfolios_single_page.return_value = {
        'PortfolioDetails': [
            {
                'DisplayName': "Not{}".format(portfolio_searching_for)
            },
            {
                'DisplayName': "StillNot{}".format(portfolio_searching_for)
            },
        ]
    }

    # exercise
    actual_response = sut.find_portfolio(mock_service_catalog, portfolio_searching_for)

    # verify
    assert expected_response == actual_response


@pytest.mark.parametrize("portfolio", [({}), ({"Description": 'Niiiice'})])
def test_create_portfolio(portfolio, mocker, sut):
    # setup
    portfolio_id = 'foo'
    portfolio_searching_for = 'my-portfolio'
    portfolios_groups_name =  'my-group'

    service_catalog = mocker.Mock()
    service_catalog.create_portfolio().get().get.return_value = portfolio_id
    expected_result = portfolio_id

    # exercise
    actual_result = sut.create_portfolio(
        service_catalog, portfolio_searching_for, portfolios_groups_name, portfolio
    )

    # verify
    assert expected_result == actual_result
    service_catalog.create_portfolio.assert_called_with(
        DisplayName=portfolio_searching_for, ProviderName=portfolios_groups_name, **portfolio
    )


def test_product_exists(mocker, sut):
    # setup
    service_catalog = mocker.Mock()
    product = {
        'Name': 'foo'
    }
    expected_result = product

    service_catalog.search_products_as_admin_single_page.return_value = {
        'ProductViewDetails': [
            {
                'ProductViewSummary': {
                    'Name': 'NotFoo'
                }
            },
            {
                'ProductViewSummary': product
            }
        ]
    }

    # exercise
    actual_result = sut.product_exists(service_catalog, product)

    # verify
    assert actual_result == expected_result


def test_product_exists_when_it_doesnt(mocker, sut):
    # setup
    service_catalog = mocker.Mock()
    product = {
        'Name': 'foo'
    }
    expected_result = None

    service_catalog.search_products_as_admin_single_page.return_value = {
        'ProductViewDetails': [
            {
                'ProductViewSummary': {
                    'Name': 'NotFoo'
                }
            }
        ]
    }

    # exercise
    actual_result = sut.product_exists(service_catalog, product)

    # verify
    assert actual_result == expected_result
