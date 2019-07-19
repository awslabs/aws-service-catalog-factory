# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from servicecatalog_factory import core
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def add_product_to_portfolio(portfolio_file_name, portfolio_display_name, product):
    """
    This function allows to you to add a product to a portfolio that exists already.  If the product contains a Source
    and it is defined as an AWS CodeCommit type then the function will ensure the repository and branch exist.

    :param portfolio_file_name: The name of the file (including .yaml) of your portfolio file.  For example ServiceCatalogFactory/portfolio/central_it.yaml should be central_it.yaml
    :param portfolio_display_name: The value of the portfolio DisplayName the product should be added to.
    :param product: a dict of the product that you want to add to the portfolio
    """
    core.add_product_to_portfolio(portfolio_file_name, portfolio_display_name, product)


def remove_product_from_portfolio(portfolio_file_name, portfolio_display_name, product_name):
    """
    This function allows to you to remove a product from a portfolio that exists already.

    :param portfolio_file_name: The name of the file (including .yaml) of your portfolio file.  For example ServiceCatalogFactory/portfolio/central_it.yaml should be central_it.yaml
    :param portfolio_display_name: The value of the portfolio DisplayName where the product exists.
    :param product_name: The name of the product you want to remove
    """
    core.remove_product_from_portfolio(portfolio_file_name, portfolio_display_name, product_name)


def add_version_to_product(portfolio_file_name, portfolio_display_name, product_name, version):
    """
    This function allows to you to add a version to product within a portfolio that exists already.
    If the version contains a Source and it is defined as an AWS CodeCommit type then the function will ensure the
    repository and branch exist.

    :param portfolio_file_name: The name of the file (including .yaml) of your portfolio file.  For example ServiceCatalogFactory/portfolio/central_it.yaml should be central_it.yaml
    :param portfolio_display_name: The value of the portfolio DisplayName the product version should be added to.
    :param product_name: The value of the product Name the version should be added to.
    :param version: a dict of the version that you want to add to the portfolio
    """
    core.add_version_to_product(portfolio_file_name, portfolio_display_name, product_name, version)


def remove_version_from_product(portfolio_file_name, portfolio_display_name, product_name, version_name):
    """
    This function allows to you to remove a version of a product within a portfolio that exists already.

    :param portfolio_file_name: The name of the file (including .yaml) of your portfolio file.  For example ServiceCatalogFactory/portfolio/central_it.yaml should be central_it.yaml
    :param portfolio_display_name: The value of the portfolio DisplayName the product version should be removed from.
    :param product_name: The value of the product Name the version should be removed from.
    :param version_name: The name of the version you want to remove
    """
    core.remove_version_from_product(portfolio_file_name, portfolio_display_name, product_name, version_name)
