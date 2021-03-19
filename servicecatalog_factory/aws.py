# Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import logging
import time

from betterboto import client as betterboto_client

logger = logging.getLogger(__file__)


def get_or_create_portfolio(
    description, provider_name, portfolio_name, tags, service_catalog
):
    found = False
    portfolio_detail = None
    list_portfolios_response = service_catalog.list_portfolios_single_page()
    logger.info(f"checking for portfolio: {portfolio_name}")
    for portfolio_detail in list_portfolios_response.get("PortfolioDetails"):
        if portfolio_detail.get("DisplayName") == portfolio_name:
            logger.info(f"found portfolio: {portfolio_name}")
            found = True
            break
    if not found:
        logger.info(f"not found portfolio, creating {portfolio_name}")
        portfolio_detail = service_catalog.create_portfolio(
            DisplayName=portfolio_name,
            Description=description,
            ProviderName=provider_name,
            Tags=tags,
        ).get("PortfolioDetail")
        logger.info(f"created {portfolio_name}")
    return portfolio_detail


def ensure_portfolio_association_for_product(portfolio_id, product_id, service_catalog):
    portfolio_details = service_catalog.list_portfolios_for_product_single_page(
        ProductId=product_id
    ).get("PortfolioDetails")
    found = False
    for portfolio_detail in portfolio_details:
        if portfolio_detail.get("Id") == portfolio_id:
            logger.info(
                f"Found an existing association between {portfolio_id} and {product_id}"
            )
            found = True
            break
    if not found:
        logger.info(f"Creating an association between {portfolio_id} and {product_id}")
        service_catalog.associate_product_with_portfolio(
            ProductId=product_id, PortfolioId=portfolio_id,
        )


def get_product(service_catalog, product_name):
    logger.info(f"Looking for product: {product_name}")
    search_products_as_admin_response = service_catalog.search_products_as_admin_single_page(
        Filters={"FullTextSearch": [product_name]}
    )
    for product_view_details in search_products_as_admin_response.get(
        "ProductViewDetails"
    ):
        product_view_summary = product_view_details.get("ProductViewSummary")
        if product_view_summary.get("Name") == product_name:
            return product_view_summary
    return None


def get_details_for_pipeline(pipeline_name):
    with betterboto_client.ClientContextManager("codepipeline") as codepipeline:
        return codepipeline.list_pipeline_executions(
            pipelineName=pipeline_name, maxResults=1
        ).get("pipelineExecutionSummaries")[0]
