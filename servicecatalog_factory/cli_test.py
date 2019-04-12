# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest
from unittest import mock

import cli as subject_under_test


class TestMerge(unittest.TestCase):
    def test_simple_case(self):
        # setup
        dict1 = {'foo': 'bar'}
        dict2 = {'bar': 'foo'}
        expected_result = {'bar': 'foo', 'foo': 'bar'}

        # exercise
        actual_result = subject_under_test.merge(dict1, dict2)

        # verify
        self.assertEqual(actual_result, expected_result)

    def test_nested(self):
        # setup
        dict1 = {'foo': {'bar': 'foo'}}
        dict2 = {'bar': 'foo'}
        expected_result = {'foo': {'bar': 'foo'}, 'bar': 'foo'}

        # exercise
        actual_result = subject_under_test.merge(dict2, dict1)

        # verify
        self.assertEqual(actual_result, expected_result)


class TestConstants(unittest.TestCase):

    def test_NON_RECOVERABLE_STATES(self):
        # setup
        expected_result = [
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

        # exercise
        actual_result = subject_under_test.NON_RECOVERABLE_STATES

        # verify
        self.assertEqual(expected_result, actual_result)


class TestCreateProduct(unittest.TestCase):
    def test_create_product(self):
        # setup
        mock_service_catalog = mock.MagicMock()

        product_id = 'prd-98y93hoih'
        create_product_response = {
            'ProductViewDetail': {
                'ProductViewSummary': {
                    'ProductId': product_id
                }
            }
        }
        mock_service_catalog.create_product.return_value = create_product_response

        search_products_as_admin_response = {
            'ProductViewDetails': [
                {'ProductViewSummary': {
                    'ProductId': product_id
                }}
            ]
        }
        mock_service_catalog.search_products_as_admin.return_value = search_products_as_admin_response

        portfolio_id = 'nkslnf-90-j3'
        portfolio = {'Id': portfolio_id}
        product_name = 'helloworld'
        product = {
            "Versions": [],
            "Options": True,
            "Id": True,
            "Source": True,
            "Name": product_name,
        }
        s3_bucket_name = 'bucky1'
        expected_result = {'ProductId': product_id}

        # exercise
        actual_result = subject_under_test.create_product(mock_service_catalog, portfolio, product, s3_bucket_name)

        # assert
        self.assertEqual(expected_result, actual_result)
        mock_service_catalog.associate_product_with_portfolio.assert_called_once_with(ProductId=product_id,
                                                                                      PortfolioId=portfolio_id)
        mock_service_catalog.search_products_as_admin.assert_called_once_with(
            Filters={'FullTextSearch': [product_name]})
        mock_service_catalog.create_product.assert_called_once_with(
            Name=product_name,
            ProductType='CLOUD_FORMATION_TEMPLATE',
            ProvisioningArtifactParameters={
                'Name': '-',
                'Type': 'CLOUD_FORMATION_TEMPLATE',
                'Description': 'Placeholder version, do not provision',
                'Info': {
                    'LoadTemplateFromURL': 'https://s3.amazonaws.com/{}/empty.template.yaml'.format(s3_bucket_name)
                }
            }
        )


class TestFindPortfolio(unittest.TestCase):

    def test_happy_path(self):
        # setup
        portfolio_searching_for = "portfolio_1"
        expected_result = {"DisplayName": portfolio_searching_for}
        service_catalog = mock.MagicMock()
        service_catalog.list_portfolios.return_value = {
            "PortfolioDetails": [expected_result]
        }

        # exercise
        actual_result = subject_under_test.find_portfolio(service_catalog, portfolio_searching_for)

        # verify
        self.assertEqual(expected_result, actual_result)

    def test_not_found_without_pagination(self):
        # setup
        expected_result = {}
        service_catalog = mock.MagicMock()
        service_catalog.list_portfolios.return_value = {
            "PortfolioDetails": [{"DisplayName": "portfolio_2"}]
        }
        portfolio_searching_for = "portfolio_1"

        # exercise
        actual_result = subject_under_test.find_portfolio(service_catalog, portfolio_searching_for)

        # verify
        self.assertEqual(expected_result, actual_result)

    def test_found_with_pagination(self):
        # setup
        portfolio_searching_for = "portfolio_1"
        expected_result = {"DisplayName": portfolio_searching_for}
        service_catalog = mock.Mock()
        service_catalog.list_portfolios.return_value = mock_response = mock.Mock(name='response')
        not_found_response = [{"DisplayName": "portfolio_2"}]
        found_response = [{"DisplayName": portfolio_searching_for}]
        page_token = "fsdfdsfdsfd"
        mock_response.get.side_effect = [
            not_found_response,
            page_token,
            page_token,
            found_response
        ]

        # exercise
        actual_result = subject_under_test.find_portfolio(service_catalog, portfolio_searching_for)

        # verify
        self.assertEqual(expected_result, actual_result)


class TestCreatePortfolio(unittest.TestCase):

    def test_happy_path(self):
        # setup
        portfolio_details_id = "1"
        portfolio_searching_for = "portfolio1"
        portfolios_groups_name = "group1"
        description = "description1"

        service_catalog = mock.MagicMock()
        service_catalog.create_portfolio().get().get.return_value = portfolio_details_id
        portfolio = {"Description": description}
        expected_result = portfolio_details_id
        expected_args = {
            'DisplayName': portfolio_searching_for,
            'ProviderName': portfolios_groups_name,
            'Description': description,
        }

        # exercise
        actual_result = subject_under_test.create_portfolio(
            service_catalog,
            portfolio_searching_for,
            portfolios_groups_name,
            portfolio
        )

        # verify
        self.assertEqual(expected_result, actual_result)
        service_catalog.create_portfolio.assert_called_with(**expected_args)

    def test_happy_path_without_description(self):
        # setup
        portfolio_details_id = "1"
        portfolio_searching_for = "portfolio1"
        portfolios_groups_name = "group1"

        service_catalog = mock.MagicMock()
        service_catalog.create_portfolio().get().get.return_value = portfolio_details_id
        portfolio = {}
        expected_result = portfolio_details_id
        expected_args = {
            'DisplayName': portfolio_searching_for,
            'ProviderName': portfolios_groups_name,
        }

        # exercise
        actual_result = subject_under_test.create_portfolio(
            service_catalog,
            portfolio_searching_for,
            portfolios_groups_name,
            portfolio
        )

        # verify
        self.assertEqual(expected_result, actual_result)
        service_catalog.create_portfolio.assert_called_with(**expected_args)


class TestProductExists(unittest.TestCase):

    def test_happy_path(self):
        # setup
        product_name = "some_product_name"
        product = {"Name": product_name}
        expected_results = product
        expected_args = {
            "Filters": {"FullTextSearch": [product_name]}
        }
        service_catalog = mock.MagicMock()
        service_catalog.search_products_as_admin.return_value = {
            "ProductViewDetails": [{"ProductViewSummary": product}]
        }

        # exercise
        actual_results = subject_under_test.product_exists(service_catalog, product)

        # verify
        self.assertEqual(expected_results, actual_results)
        service_catalog.search_products_as_admin.assert_called_once_with(**expected_args)

    def test_happy_path_with_pagination(self):
        # setup
        product_name = "some_product_name"
        matching_product = {"Name": product_name}
        not_product_name = "some_product_name1"
        not_matching_product = {"Name": not_product_name}
        expected_results = matching_product
        expected_args = {
            "Filters": {"FullTextSearch": [product_name]}
        }
        service_catalog = mock.MagicMock()
        response_mock = mock.MagicMock(name='response')
        page_token = 'sdfdijfhds'
        response_mock.get.side_effect = [
            [{"ProductViewSummary": not_matching_product}],
            page_token,
            page_token,
            [{"ProductViewSummary": matching_product}],
        ]
        service_catalog.search_products_as_admin.return_value = response_mock

        # exercise
        actual_results = subject_under_test.product_exists(service_catalog, matching_product)

        # verify
        self.assertEqual(expected_results, actual_results)
        self.assertEqual(2, service_catalog.search_products_as_admin.call_count)

        args, kwargs = service_catalog.search_products_as_admin.call_args_list[0]
        self.assertEqual(expected_args, kwargs)

        args, kwargs = service_catalog.search_products_as_admin.call_args_list[1]
        self.assertEqual({'Filters': {'FullTextSearch': ['some_product_name']}, 'PageToken': 'sdfdijfhds'}, kwargs)

    def test_not_found(self):
        # setup
        product_name = "some_product_name"
        service_catalog = mock.MagicMock()
        service_catalog.search_products_as_admin.return_value = {
            "ProductViewDetails": [{"ProductViewSummary": {"Name": product_name}}]
        }

        # exercise
        actual_results = subject_under_test.product_exists(service_catalog, {"Name": "some_other_product"})

        # verify
        self.assertIsNone(actual_results)


class TestGetBucketName(unittest.TestCase):

    @mock.patch('cli.boto3.client')
    def test_get_bucket_name(self, mock_client):
        # setup
        expected_result = bucket_name = "bucky1"
        mock_client().describe_stacks.return_value = {
            'Stacks': [
                {
                    "Outputs": [
                        {"OutputKey": "CatalogBucketName", "OutputValue": bucket_name}
                    ]
                }
            ]
        }

        # exercise
        actual_result = subject_under_test.get_bucket_name()

        # verify
        self.assertEqual(actual_result, expected_result)

    @mock.patch('cli.boto3.client')
    def test_get_bucket_name_fails(self, mock_client):
        # setup
        expected_result = bucket_name = "bucky1"
        mock_client().describe_stacks.return_value = {
            'Stacks': [
                {
                    "Outputs": [
                        {"OutputKey": "CatalogBucketName2", "OutputValue": bucket_name}
                    ]
                }
            ]
        }

        # exercise
        with self.assertRaises(AssertionError) as cm:
            subject_under_test.get_bucket_name()

        # verify
        self.assertEqual('Could not find bucket', str(cm.exception))


class TestEnsurePortfolio(unittest.TestCase):

    @mock.patch('cli.create_portfolio')
    @mock.patch('cli.find_portfolio')
    def test_ensure_portfolio_when_it_does_exist(self, mock_find_portfolio, mock_create_portfolio):
        # setup
        expected_id = 'port-sionfoid'

        portfolios_groups_name = 'foo'
        display_name = 'bar'
        portfolio = {
            'DisplayName': display_name
        }
        mock_find_portfolio.return_value = {
            'Id': expected_id
        }

        # exercise
        subject_under_test.ensure_portfolio(portfolios_groups_name, portfolio)

        # verify
        self.assertEqual(expected_id, portfolio.get('Id'))

    @mock.patch('cli.create_portfolio')
    @mock.patch('cli.find_portfolio')
    def test_ensure_portfolio_when_it_does_not_exist(self, mock_find_portfolio, mock_create_portfolio):
        # setup
        expected_id = 'port-sionfoid'

        portfolios_groups_name = 'foo'
        display_name = 'bar'
        portfolio = {
            'DisplayName': display_name
        }
        mock_find_portfolio.return_value = {
            'Id': None
        }
        mock_create_portfolio.return_value = expected_id

        # exercise
        subject_under_test.ensure_portfolio(portfolios_groups_name, portfolio)

        # verify
        self.assertEqual(expected_id, portfolio.get('Id'))


class TestEnsureProduct(unittest.TestCase):

    @mock.patch('cli.get_bucket_name')
    @mock.patch('cli.product_exists')
    @mock.patch('cli.boto3.client')
    def test_ensure_product_when_exists(self, mock_service_catalog, mock_product_exists, mock_get_bucket_name):
        # setup
        product = {}
        portfolio = {}
        product_id = 'prd-jdbibd'
        mock_product_exists.return_value = {
            'ProductId': product_id
        }

        # exercise
        subject_under_test.ensure_product(product, portfolio)

        # verify
        self.assertEqual(product_id, product.get('Id'))
        mock_get_bucket_name.assert_called_once()
        mock_product_exists.assert_called_once_with(mock_service_catalog(), product)

    @mock.patch('cli.create_product')
    @mock.patch('cli.get_bucket_name')
    @mock.patch('cli.product_exists')
    @mock.patch('cli.boto3.client')
    def test_ensure_product_when_not_exists(
            self, mock_service_catalog, mock_product_exists, mock_get_bucket_name, mock_create_product
    ):
        # setup
        product = {}
        portfolio = {}
        product_id = 'prd-jdbibd'
        mock_product_exists.return_value = None
        mock_get_bucket_name.return_value = bucket_name = 'dsdjosdso'
        mock_create_product.return_value = {
            'ProductId': product_id
        }

        # exercise
        subject_under_test.ensure_product(product, portfolio)

        # verify
        self.assertEqual(product_id, product.get('Id'))
        mock_get_bucket_name.assert_called_once()
        mock_product_exists.assert_called_once_with(mock_service_catalog(), product)
        mock_create_product.assert_called_once_with(mock_service_catalog(), portfolio, product, bucket_name)


class TestGeneratePipeline(unittest.TestCase):

    @mock.patch('cli.ensure_portfolio')
    @mock.patch('cli.ensure_product')
    def test_generate_pipeline(self, mock_ensure_product, mock_ensure_portfolio):
        # setup
        template = mock.MagicMock()
        portfolios_groups_name = mock.MagicMock()
        output_path = mock.MagicMock()
        version = mock.MagicMock()
        product = mock.MagicMock()
        portfolio = mock.MagicMock()

        # exercise
        subject_under_test.generate_pipeline(
            template, portfolios_groups_name, output_path, version, product, portfolio
        )

        # verify
