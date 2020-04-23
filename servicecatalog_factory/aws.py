# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import functools
import logging
import time

from betterboto import client as betterboto_client

from . import constants

logger = logging.getLogger(__file__)


def get_or_create_portfolio(description, provider_name, portfolio_name, tags, service_catalog):
    found = False
    portfolio_detail = None
    list_portfolios_response = service_catalog.list_portfolios_single_page()
    logger.info(f"checking for portfolio: {portfolio_name}")
    for portfolio_detail in list_portfolios_response.get('PortfolioDetails'):
        if portfolio_detail.get('DisplayName') == portfolio_name:
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
        ).get('PortfolioDetail')
        logger.info(f"created {portfolio_name}")
    return portfolio_detail


def get_or_create_product(name, args, service_catalog):
    logger.info(f'Looking for product: {name}')
    search_products_as_admin_response = service_catalog.search_products_as_admin_single_page(
        Filters={'FullTextSearch': [name]}
    )
    found = False
    product_view_summary = None
    for product_view_details in search_products_as_admin_response.get('ProductViewDetails'):
        product_view_summary = product_view_details.get('ProductViewSummary')
        if product_view_summary.get('Name') == name:
            found = True
            logger.info(f'Found product: {name}: {product_view_summary}')
            break
    if not found:
        logger.info(f'Not found product: {name}, creating')

        product_view_summary = service_catalog.create_product(
            **args
        ).get('ProductViewDetail').get('ProductViewSummary')
        product_id = product_view_summary.get('ProductId')
        logger.info(f"Created product {name}, waiting for completion")
        while True:
            time.sleep(2)
            search_products_as_admin_response = service_catalog.search_products_as_admin_single_page()
            products_ids = [
                product_view_detail.get('ProductViewSummary').get('ProductId') for product_view_detail in
                search_products_as_admin_response.get('ProductViewDetails')
            ]
            logger.info(f'Looking for {product_id} in {products_ids}')
            if product_id in products_ids:
                logger.info(f'Found {product_id} ')
                break
    return product_view_summary


def delete_product(product_name, service_catalog, region):
    logger.info(f'Looking for product to delete: {product_name}')
    search_products_as_admin_response = service_catalog.search_products_as_admin_single_page(
        Filters={'FullTextSearch': [product_name]}
    )
    found_product_id = False
    product_view_summary = None
    for product_view_details in search_products_as_admin_response.get('ProductViewDetails'):
        product_view_summary = product_view_details.get('ProductViewSummary')
        if product_view_summary.get('Name') == product_name:
            found_product = True
            logger.info(f'Found product: {product_name}: {product_view_summary}')
            break

    if found_product:
        product_id = product_view_summary.get('ProductId')

        list_portfolios_response = service_catalog.list_portfolios_for_product_single_page(
            ProductId=product_id,
        )
        portfolio_ids = [portfolio_detail['Id'] for portfolio_detail in list_portfolios_response.get('PortfolioDetails')]
        portfolio_names = [portfolio_detail['Name'] for portfolio_detail in list_portfolios_response.get('PortfolioDetails')]

        #get all versions to be able to delete their pipeline stacks
        list_versions_response = service_catalog.list_provisioning_artifacts_single_page(
            ProductId=product_id
        )

        version_names = [version['Name'] for version in list_versions_response.get('ProvisioningArtifactDetails')]
        if version_names:
            logger.info(f'Deleting Pipeline stacks for versions: {version_names} of {product_name}')
            
            cloudformation_stacks = []
            with betterboto_client.ClientContextManager('cloudformation', region_name=region) as cloudformation:
                list_stacks_response = cloudformation.list_stacks()
                cloudformation_stacks.append(list_stacks_response['StackSummaries'])
                while 'NextToken' in list_stacks_response:
                    list_stacks_response = cloudformation.list_stacks()
                    cloudformation_stacks.append(list_stacks_response['StackSummaries'])

                cloudformation_stack_names = [stack['StackName'] for stack in cloudformation_stacks]

                for version_name in version_names:
                    for portfolio_name in portfolio_names:
                        stack_name = "-".join([portfolio_name, product_name, version_name])
                        if stack_name in cloudformation_stack_names:
                            logger.info("Deleting pipeline stack: {}".format(stack_name))
                            cloudformation.delete_stack(StackName=stack_name)
                            waiter = cloudformation.get_waiter('stack_delete_complete')
                            waiter.wait(StackName=stack_name)

        for portfolio_id in portfolio_ids:
            logger.info(f'Disassociating {name} {product_id} from {portfolio_id}')
            service_catalog.disassociate_product_from_portfolio(
                ProductId=product_id,
                PortfolioId=portfolio_id
            )

        logger.info(f'Deleting {name} {product_id} from {portfolio_id}')

        service_catalog.delete_product(
            ProductId=product_id,
        )

        logger.info(f'Finished Deleting {name}')
        

def ensure_portfolio_association_for_product(portfolio_id, product_id, service_catalog):
    portfolio_details = service_catalog.list_portfolios_for_product_single_page(
        ProductId=product_id
    ).get('PortfolioDetails')
    found = False
    for portfolio_detail in portfolio_details:
        if portfolio_detail.get('Id') == portfolio_id:
            logger.info(f"Found an existing association between {portfolio_id} and {product_id}")
            found = True
            break
    if not found:
        logger.info(f"Creating an association between {portfolio_id} and {product_id}")
        service_catalog.associate_product_with_portfolio(
            ProductId=product_id,
            PortfolioId=portfolio_id,
        )


def get_product(service_catalog, product_name):
    logger.info(f'Looking for product: {product_name}')
    search_products_as_admin_response = service_catalog.search_products_as_admin_single_page(
        Filters={'FullTextSearch': [product_name]}
    )
    for product_view_details in search_products_as_admin_response.get('ProductViewDetails'):
        product_view_summary = product_view_details.get('ProductViewSummary')
        if product_view_summary.get('Name') == product_name:
            return product_view_summary
    return None


def get_details_for_pipeline(pipeline_name):
    with betterboto_client.ClientContextManager('codepipeline') as codepipeline:
        return codepipeline.list_pipeline_executions(
            pipelineName=pipeline_name, maxResults=1
        ).get('pipelineExecutionSummaries')[0]
