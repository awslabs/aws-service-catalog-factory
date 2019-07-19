# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from servicecatalog_factory import core
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def add_product_to_portfolio(portfolio_file_name, portfolio_display_name, product):
    core.add_product_to_portfolio(portfolio_file_name, portfolio_display_name, product)


def remove_product_from_portfolio(portfolio_file_name, portfolio_display_name, product):
    core.remove_product_from_portfolio(portfolio_file_name, portfolio_display_name, product)


def add_version_to_product(portfolio_file_name, portfolio_display_name, product_name, version):
    core.add_version_to_product(portfolio_file_name, portfolio_display_name, product_name, version)


def remove_version_from_product(portfolio_file_name, portfolio_display_name, product_name, version):
    core.remove_version_from_product(portfolio_file_name, portfolio_display_name, product_name, version)
