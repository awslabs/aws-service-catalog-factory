# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import hashlib
import logging
import os
import time

import boto3
import click
import yaml
from jinja2 import Environment, FileSystemLoader, Template
from pykwalify.core import Core
import collections
from copy import deepcopy
from betterboto import client as betterboto_client
from threading import Thread
import shutil
import pkg_resources
import requests

CONFIG_PARAM_NAME = "/servicecatalog-factory/config"
PUBLISHED_VERSION = pkg_resources.require("aws-service-catalog-factory")[0].version
VERSION = PUBLISHED_VERSION

BOOTSTRAP_STACK_NAME = 'servicecatalog-factory'
SERVICE_CATALOG_FACTORY_REPO_NAME = 'ServiceCatalogFactory'

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

HOME_REGION = os.environ.get('AWS_DEFAULT_REGION', 'eu-west-1')

NON_RECOVERABLE_STATES = [
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

COMPONENT = 'component.j2'
COMPONENT_GROUP = 'component_group.j2'
ASSOCIATIONS = 'associations.j2'


def resolve_from_site_packages(what):
    return os.path.sep.join([
        os.path.dirname(os.path.abspath(__file__)),
        what
    ])


def read_from_site_packages(what):
    return open(
        resolve_from_site_packages(what),
        'r'
    ).read()


TEMPLATE_DIR = resolve_from_site_packages('templates')
ENV = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    extensions=['jinja2.ext.do'],
)


def get_regions():
    with betterboto_client.ClientContextManager('ssm', region_name=HOME_REGION) as ssm:
        response = ssm.get_parameter(Name=CONFIG_PARAM_NAME)
        config = yaml.safe_load(response.get('Parameter').get('Value'))
        return config.get('regions')


def merge(dict1, dict2):
    result = deepcopy(dict1)
    for key, value in dict2.items():
        if isinstance(value, collections.Mapping):
            result[key] = merge(result.get(key, {}), value)
        else:
            result[key] = deepcopy(dict2[key])
    return result


def find_portfolio(service_catalog, portfolio_searching_for):
    LOGGER.info('Searching for portfolio for: {}'.format(portfolio_searching_for))
    response = service_catalog.list_portfolios_single_page()
    for detail in response.get('PortfolioDetails'):
        if detail.get('DisplayName') == portfolio_searching_for:
            LOGGER.info('Found portfolio: {}'.format(portfolio_searching_for))
            return detail
    return {}


def create_portfolio(service_catalog, portfolio_searching_for, portfolios_groups_name, portfolio):
    LOGGER.info('Creating portfolio: {}'.format(portfolio_searching_for))
    args = {
        'DisplayName': portfolio_searching_for,
        'ProviderName': portfolios_groups_name,
    }
    if portfolio.get('Description'):
        args['Description'] = portfolio.get('Description')
    return service_catalog.create_portfolio(
        **args
    ).get('PortfolioDetail').get('Id')


def product_exists(service_catalog, product, **kwargs):
    product_to_find = product.get('Name')
    LOGGER.info('Searching for product for: {}'.format(product_to_find))
    response = service_catalog.search_products_as_admin_single_page(
        Filters={'FullTextSearch': [product_to_find]}
    )
    for product_view_details in response.get('ProductViewDetails'):
        product_view = product_view_details.get('ProductViewSummary')
        if product_view.get('Name') == product_to_find:
            LOGGER.info('Found product: {}'.format(product_view))
            return product_view


def create_product(service_catalog, portfolio, product, s3_bucket_name):
    LOGGER.info('Creating a product: {}'.format(product.get('Name')))
    args = product.copy()
    args.update({
        'ProductType': 'CLOUD_FORMATION_TEMPLATE',
        'ProvisioningArtifactParameters': {
            'Name': "-",
            'Type': 'CLOUD_FORMATION_TEMPLATE',
            'Description': 'Placeholder version, do not provision',
            "Info": {
                "LoadTemplateFromURL": "https://s3.amazonaws.com/{}/{}".format(
                    s3_bucket_name, "empty.template.yaml"
                )
            }
        }
    })
    del args['Versions']
    if args.get('Options'):
        del args['Options']
    if args.get('Id'):
        del args['Id']
    if args.get('Source'):
        del args['Source']

    LOGGER.info("Creating a product: {}".format(args))
    response = service_catalog.create_product(
        **args
    )
    product_view = response.get('ProductViewDetail').get('ProductViewSummary')
    product_id = product_view.get('ProductId')

    # create_product is not a synchronous request and describe product doesnt work here
    LOGGER.info('Waiting for the product to register: {}'.format(product.get('Name')))
    found = False
    while not found:
        response = service_catalog.search_products_as_admin_single_page(
            Filters={'FullTextSearch': [args.get("Name")]}
        )
        time.sleep(1)
        product_view_details = response.get('ProductViewDetails')
        for product_view_detail in product_view_details:
            found = product_view_detail.get('ProductViewSummary').get('ProductId') == product_id
            break

    service_catalog.associate_product_with_portfolio(
        ProductId=product_id,
        PortfolioId=portfolio.get('Id')
    )
    return product_view


def get_bucket_name():
    s3_bucket_url = None
    with betterboto_client.ClientContextManager(
            'cloudformation', region_name=HOME_REGION
    ) as cloudformation:
        response = cloudformation.describe_stacks(
            StackName=BOOTSTRAP_STACK_NAME
        )
        assert len(response.get('Stacks')) == 1, "There should only be one stack with the name"
        outputs = response.get('Stacks')[0].get('Outputs')
        for output in outputs:
            if output.get('OutputKey') == "CatalogBucketName":
                s3_bucket_url = output.get('OutputValue')
        assert s3_bucket_url is not None, "Could not find bucket"
        return s3_bucket_url


def ensure_portfolio(portfolios_groups_name, portfolio, service_catalog):
    portfolio_searching_for = "{}-{}".format(portfolios_groups_name, portfolio.get('DisplayName'))
    remote_portfolio = find_portfolio(service_catalog, portfolio_searching_for)
    if remote_portfolio.get('Id') is None:
        LOGGER.info("Couldn't find portfolio, creating one for: {}".format(portfolio_searching_for))
        portfolio['Id'] = create_portfolio(
            service_catalog,
            portfolio_searching_for,
            portfolios_groups_name,
            portfolio
        )
    else:
        portfolio['Id'] = remote_portfolio.get('Id')


def ensure_product(product, portfolio, service_catalog):
    s3_bucket_name = get_bucket_name()

    remote_product = product_exists(service_catalog, product)
    if remote_product is None:
        remote_product = create_product(
            service_catalog,
            portfolio,
            product,
            s3_bucket_name,
        )
    product['Id'] = remote_product.get('ProductId')


def generate_and_run(portfolios_groups_name, portfolio, what, stack_name, region, portfolio_id):
    LOGGER.info("Generating: {} for: {} in region: {}".format(
        what, portfolio.get('DisplayName'), region
    ))
    template = ENV.get_template(what).render(
        portfolio=portfolio, portfolio_id=portfolio_id
    )
    stack_name = "-".join([portfolios_groups_name, portfolio.get('DisplayName'), stack_name])
    with betterboto_client.ClientContextManager(
            'cloudformation', region_name=region
    ) as cloudformation:
        cloudformation.create_or_update(
            StackName=stack_name,
            TemplateBody=template,
            Capabilities=['CAPABILITY_IAM'],
        )
        LOGGER.info("Finished creating/updating: {}".format(stack_name))


def ensure_product_versions_active_is_correct(product, service_catalog):
    LOGGER.info("Ensuring product version active setting is in sync for: {}".format(product.get('Name')))
    product_id = product.get('Id')
    response = service_catalog.list_provisioning_artifacts(
        ProductId=product_id
    )
    for version in product.get('Versions', []):
        LOGGER.info('Checking for version: {}'.format(version.get('Name')))
        active = version.get('Active', True)
        LOGGER.info("Checking through: {}".format(response))
        for provisioning_artifact_detail in response.get('ProvisioningArtifactDetails', []):
            if provisioning_artifact_detail.get('Name') == version.get('Name'):
                LOGGER.info("Found matching")
                if provisioning_artifact_detail.get('Active') != active:
                    LOGGER.info("Active status needs to change")
                    service_catalog.update_provisioning_artifact(
                        ProductId=product_id,
                        ProvisioningArtifactId=provisioning_artifact_detail.get('Id'),
                        Active=active,
                    )


def generate_pipeline(template, portfolios_groups_name, output_path, version, product, portfolio):
    LOGGER.info('Generating pipeline for {}:{}'.format(
        portfolios_groups_name, product.get('Name')
    ))
    product_ids_by_region = {}
    portfolio_ids_by_region = {}
    all_regions = get_regions()
    for region in all_regions:
        with betterboto_client.ClientContextManager(
                'servicecatalog', region_name=region
        ) as service_catalog:
            ensure_portfolio(portfolios_groups_name, portfolio, service_catalog)
            portfolio_ids_by_region[region] = portfolio.get('Id')
            ensure_product(product, portfolio, service_catalog)
            ensure_product_versions_active_is_correct(product, service_catalog)
            product_ids_by_region[region] = product.get('Id')
    friendly_uid = "-".join(
        [
            portfolios_groups_name,
            portfolio.get('DisplayName'),
            product.get('Name'),
            version.get('Name')
        ]
    )

    rendered = template.render(
        friendly_uid=friendly_uid,
        portfolios_groups_name=portfolios_groups_name,
        version=version,
        product=product,
        portfolio=portfolio,
        Options=merge(product.get('Options', {}), version.get('Options', {})),
        Source=merge(product.get('Source', {}), version.get('Source', {})),
        ProductIdsByRegion=product_ids_by_region,
        PortfolioIdsByRegion=portfolio_ids_by_region,
        ALL_REGIONS=all_regions,
    )
    rendered = Template(rendered).render(
        friendly_uid=friendly_uid,
        portfolios_groups_name=portfolios_groups_name,
        version=version,
        product=product,
        portfolio=portfolio,
        Options=merge(product.get('Options', {}), version.get('Options', {})),
        Source=merge(product.get('Source', {}), version.get('Source', {})),
        ProductIdsByRegion=product_ids_by_region,
        PortfolioIdsByRegion=portfolio_ids_by_region,
        ALL_REGIONS=all_regions,
    )

    output_file_path = os.path.sep.join([output_path, friendly_uid + ".template.yaml"])
    with open(output_file_path, 'w') as output_file:
        output_file.write(rendered)

    return portfolio_ids_by_region, product_ids_by_region


def generate_pipelines(portfolios_groups_name, portfolios, output_path):
    LOGGER.info('Generating pipelines for {}'.format(portfolios_groups_name))
    os.makedirs(output_path)
    all_regions = get_regions()
    for portfolio in portfolios.get('Portfolios'):
        portfolio_ids_by_region = {}
        for product in portfolio.get('Components', []):
            for version in product.get('Versions'):
                portfolio_ids_by_region_for_component, product_ids_by_region = generate_pipeline(
                    ENV.get_template(COMPONENT),
                    portfolios_groups_name,
                    output_path,
                    version,
                    product,
                    portfolio,
                )
                portfolio_ids_by_region.update(portfolio_ids_by_region_for_component)
        for product in portfolio.get('ComponentGroups', []):
            for version in product.get('Versions'):
                portfolio_ids_by_region_for_group, product_ids_by_region = generate_pipeline(
                    ENV.get_template(COMPONENT_GROUP),
                    portfolios_groups_name,
                    output_path,
                    version,
                    product,
                    portfolio,
                )
                portfolio_ids_by_region.update(portfolio_ids_by_region_for_group)
        threads = []
        for region in all_regions:
            process = Thread(
                name=region,
                target=generate_and_run,
                args=[
                    portfolios_groups_name,
                    portfolio,
                    ASSOCIATIONS,
                    'associations',
                    region,
                    portfolio_ids_by_region[region]
                ]
            )
            process.start()
            threads.append(process)
            for process in threads:
                process.join()


@click.group()
@click.option('--info/--no-info', default=False)
@click.option('--info-line-numbers/--no-info-line-numbers', default=False)
def cli(info, info_line_numbers):
    """cli for pipeline tools"""
    if info:
        logging.basicConfig(
            format='%(levelname)s %(threadName)s %(message)s', level=logging.INFO
        )
    if info_line_numbers:
        logging.basicConfig(
            format='%(levelname)s %(threadName)s [%(filename)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d:%H:%M:%S',
            level=logging.INFO
        )


@cli.command()
@click.argument('p', type=click.Path(exists=True))
def validate(p):
    for portfolio_file_name in os.listdir(p):
        portfolios_file_path = os.path.sep.join([p, portfolio_file_name])
        LOGGER.info('Validating {}'.format(portfolios_file_path))
        core = Core(
            source_file=portfolios_file_path,
            schema_files=[resolve_from_site_packages('schema.yaml')]
        )
        core.validate(raise_exception=True)
        click.echo("Finished validating: {}".format(portfolios_file_path))
    click.echo("Finished validating: OK")


@cli.command()
@click.argument('p', type=click.Path(exists=True))
def generate(p):
    LOGGER.info('Generating')
    for portfolio_file_name in os.listdir(p):
        p_name = portfolio_file_name.split(".")[0]
        output_path = os.path.sep.join(["output", p_name])
        portfolios_file_path = os.path.sep.join([p, portfolio_file_name])
        with open(portfolios_file_path) as portfolios_file:
            portfolios_file_contents = portfolios_file.read()
            portfolios = yaml.safe_load(portfolios_file_contents)
            generate_pipelines(p_name, portfolios, output_path)


def get_stacks():
    with betterboto_client.ClientContextManager('cloudformation') as cloudformation:
        stack_summaries = []
        args = {
            "StackStatusFilter": [
                'CREATE_IN_PROGRESS',
                'CREATE_FAILED',
                'CREATE_COMPLETE',
                'ROLLBACK_IN_PROGRESS',
                'ROLLBACK_FAILED',
                'ROLLBACK_COMPLETE',
                'DELETE_IN_PROGRESS',
                'DELETE_FAILED',
                'UPDATE_IN_PROGRESS',
                'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS',
                'UPDATE_COMPLETE',
                'UPDATE_ROLLBACK_IN_PROGRESS',
                'UPDATE_ROLLBACK_FAILED',
                'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS',
                'UPDATE_ROLLBACK_COMPLETE',
                'REVIEW_IN_PROGRESS',
            ]
        }
        while True:
            response = cloudformation.list_stacks(
                **args
            )
            stack_summaries += response.get('StackSummaries')
            if response.get('NextToken'):
                args['NextToken'] = response.get('NextToken')
            else:
                break

        results = {}
        for stack_summary in stack_summaries:
            results[stack_summary.get('StackName')] = stack_summary.get('StackStatus')
        return results


@cli.command()
@click.argument('p', type=click.Path(exists=True))
def deploy(p):
    stacks = get_stacks()
    for portfolio_file_name in os.listdir(p):
        p_name = portfolio_file_name.split(".")[0]
        output_path = os.path.sep.join(["output", p_name])
        portfolios_file_path = os.path.sep.join([p, portfolio_file_name])
        with open(portfolios_file_path) as portfolios_file:
            portfolios_file_contents = portfolios_file.read()
            portfolios = yaml.safe_load(portfolios_file_contents)
            for portfolio in portfolios.get('Portfolios'):
                for product in portfolio.get('Components', []):
                    for version in product.get('Versions'):
                        run_deploy_for_component(
                            p_name,
                            output_path,
                            portfolio,
                            product,
                            version,
                            stacks,
                        )
                for product in portfolio.get('ComponentGroups', []):
                    for version in product.get('Versions'):
                        run_deploy_for_component_groups(
                            p_name,
                            output_path,
                            portfolio,
                            product,
                            version,
                            stacks,
                        )


def get_hash_for_template(template):
    hasher = hashlib.md5()
    hasher.update(str.encode(template))
    return "{}{}".format('a', hasher.hexdigest())


def run_deploy_for_component_groups(group_name, path, portfolio, product, version, stacks):
    friendly_uid = "-".join([
        group_name, portfolio.get('DisplayName'), product.get('Name'), version.get('Name')
    ])
    first_run_of_stack = stacks.get(friendly_uid, False) is False
    LOGGER.info('Running deploy for: {}. Is first run: {}'.format(
        friendly_uid, first_run_of_stack
    ))

    staging_template_path = os.path.sep.join([path, "{}.template.yaml".format(friendly_uid)])
    with open(staging_template_path) as staging_template:
        staging_template_contents = staging_template.read()
    s3_bucket_name = get_bucket_name()
    s3 = boto3.resource('s3')
    template_path = "{}/{}/product.template.yaml".format(product.get('Name'), version.get('Name'))
    obj = s3.Object(s3_bucket_name, template_path)
    obj.put(Body=staging_template_contents)

    with betterboto_client.ClientContextManager('servicecatalog') as service_catalog:
        product_to_find = product.get('Name')

        response = service_catalog.search_products_as_admin_single_page(
            Filters={'FullTextSearch': [product_to_find]}
        )
        product_id = None
        for product_view_details in response.get('ProductViewDetails'):
            product_view = product_view_details.get('ProductViewSummary')
            if product_view.get('Name') == product_to_find:
                LOGGER.info('Found product: {}'.format(product_view))
                product_id = product_view.get("ProductId")
                break

        assert product_id is not None, "Could not find product"

        found = False
        response = service_catalog.list_provisioning_artifacts_single_page(ProductId=product_id)
        for provisioning_artifact_detail in response.get('ProvisioningArtifactDetails'):
            if provisioning_artifact_detail.get('Name') == version.get("Name"):
                found = True

        if not found:
            LOGGER.info("Creating version: {}. It didn't exist".format(version.get("Name")))
            create_args = {
                "ProductId": product_id,
                "Parameters": {
                    'Name': version.get('Name'),
                    'Info': {
                        "LoadTemplateFromURL": "https://s3.amazonaws.com/{}/{}".format(
                            s3_bucket_name, template_path
                        )
                    },
                    'Type': 'CLOUD_FORMATION_TEMPLATE'
                }
            }
            if version.get("Description"):
                create_args['Parameters']['Description'] = version.get("Description")
            service_catalog.create_provisioning_artifact(**create_args)
        else:
            LOGGER.info(
                'Skipped creating version: {}. It already exists'.format(version.get("Name"))
            )


def run_deploy_for_component(group_name, path, portfolio, product, version, stacks):
    friendly_uid = "-".join([
        group_name,
        portfolio.get('DisplayName'),
        product.get('Name'),
        version.get('Name')
    ])
    first_run_of_stack = stacks.get(friendly_uid, False) is False
    LOGGER.info(
        'Running deploy for: {}. Is first run: {}'.format(friendly_uid, first_run_of_stack)
    )

    staging_template_path = os.path.sep.join([path, "{}.template.yaml".format(friendly_uid)])
    with open(staging_template_path) as staging_template:
        staging_template_contents = staging_template.read()

    with betterboto_client.ClientContextManager('cloudformation') as cloudformation:
        cloudformation.create_or_update(
            StackName=friendly_uid,
            TemplateBody=staging_template_contents,
        )
        LOGGER.info('Finished stack: {}'.format(friendly_uid))


@cli.command()
@click.argument('portfolio-name')
@click.argument('product')
@click.argument('version')
def nuke_product_version(portfolio_name, product, version):
    click.echo("Nuking service catalog traces")
    with betterboto_client.ClientContextManager('servicecatalog') as servicecatalog:
        response = servicecatalog.list_portfolios_single_page()
        portfolio_id = None
        for portfolio_detail in response.get('PortfolioDetails'):
            if portfolio_detail.get('DisplayName') == portfolio_name:
                portfolio_id = portfolio_detail.get('Id')
                break
        if portfolio_id is None:
            raise Exception("Could not find your portfolio: {}".format(portfolio_name))
        else:
            LOGGER.info('Portfolio_id found: {}'.format(portfolio_id))
            product_name = "-".join([product, version])
            LOGGER.info('Looking for product: {}'.format(product_name))
            result = product_exists(servicecatalog, {'Name': product}, PortfolioId=portfolio_id)
            if result is None:
                click.echo("Could not find product: {}".format(product))
            else:
                product_id = result.get('ProductId')
                LOGGER.info("p: {}".format(product_id))

                LOGGER.info('Looking for version: {}'.format(version))
                response = servicecatalog.list_provisioning_artifacts(
                    ProductId=product_id,
                )

                version_id = None
                for provisioning_artifact_detail in response.get('ProvisioningArtifactDetails'):
                    if provisioning_artifact_detail.get('Name') == version:
                        version_id = provisioning_artifact_detail.get('Id')
                if version_id is None:
                    click.echo('Could not find version: {}'.format(version))
                else:
                    LOGGER.info('Found version: {}'.format(version_id))
                    LOGGER.info('Deleting version: {}'.format(version_id))
                    servicecatalog.delete_provisioning_artifact(
                        ProductId=product_id,
                        ProvisioningArtifactId=version_id
                    )
                    click.echo('Deleted version: {}'.format(version_id))
    click.echo("Finished nuking service catalog traces")

    click.echo('Nuking pipeline traces')
    nuke_stack(portfolio_name, product, version)
    click.echo('Finished nuking pipeline traces')


def nuke_stack(portfolio_name, product, version):
    with betterboto_client.ClientContextManager('cloudformation') as cloudformation:
        stack_name = "-".join([portfolio_name, product, version])
        click.echo("Nuking stack: {}".format(stack_name))
        try:
            cloudformation.describe_stacks(StackName=stack_name)
            cloudformation.delete_stack(StackName=stack_name)
            waiter = cloudformation.get_waiter('stack_delete_complete')
            waiter.wait(StackName=stack_name)
        except cloudformation.exceptions.ClientError as e:
            if "Stack with id {} does not exist".format(stack_name) in str(e):
                click.echo("Could not see stack")
            else:
                raise e


@cli.command()
@click.argument('branch-name')
def bootstrap_branch(branch_name):
    global VERSION
    VERSION = "https://github.com/awslabs/aws-service-catalog-factory/archive/{}.zip".format(branch_name)
    do_bootstrap()


@cli.command()
def bootstrap():
    do_bootstrap()


def do_bootstrap():
    click.echo('Starting bootstrap')
    click.echo('Starting regional deployments')
    all_regions = get_regions()
    with betterboto_client.MultiRegionClientContextManager(
            'cloudformation', all_regions
    ) as clients:
        LOGGER.info('Creating {}-regional'.format(BOOTSTRAP_STACK_NAME))
        threads = []
        template = read_from_site_packages(
            '{}.template.yaml'.format('{}-regional'.format(BOOTSTRAP_STACK_NAME))
        )
        template = Template(template).render(VERSION=VERSION)
        args = {
            'StackName': '{}-regional'.format(BOOTSTRAP_STACK_NAME),
            'TemplateBody': template,
            'Capabilities': ['CAPABILITY_IAM'],
            'Parameters': [
                {
                    'ParameterKey': 'Version',
                    'ParameterValue': VERSION,
                    'UsePreviousValue': False,
                },
            ],
        }
        for client_region, client in clients.items():
            process = Thread(name=client_region, target=client.create_or_update, kwargs=args)
            process.start()
            threads.append(process)
        for process in threads:
            process.join()
        LOGGER.info('Finished creating {}-regional'.format(BOOTSTRAP_STACK_NAME))
    click.echo('Completed regional deployments')

    click.echo('Starting main deployment')
    s3_bucket_name = None
    with betterboto_client.ClientContextManager('cloudformation') as cloudformation:
        LOGGER.info('Creating {}'.format(BOOTSTRAP_STACK_NAME))
        template = read_from_site_packages('{}.template.yaml'.format(BOOTSTRAP_STACK_NAME))
        template = Template(template).render(VERSION=VERSION)
        args = {
            'StackName': BOOTSTRAP_STACK_NAME,
            'TemplateBody': template,
            'Capabilities': ['CAPABILITY_NAMED_IAM'],
            'Parameters': [
                {
                    'ParameterKey': 'Version',
                    'ParameterValue': VERSION,
                    'UsePreviousValue': False,
                },
            ],
        }
        cloudformation.create_or_update(**args)
        response = cloudformation.describe_stacks(StackName=BOOTSTRAP_STACK_NAME)
        assert len(response.get('Stacks')) == 1, "Error code 1"
        stack_outputs = response.get('Stacks')[0]['Outputs']
        for stack_output in stack_outputs:
            if stack_output.get('OutputKey') == 'CatalogBucketName':
                s3_bucket_name = stack_output.get('OutputValue')
                break
        LOGGER.info(
            'Finished creating {}. CatalogBucketName is: {}'.format(
                BOOTSTRAP_STACK_NAME, s3_bucket_name
            )
        )

    LOGGER.info('Adding empty product template to s3')
    template = open(resolve_from_site_packages('empty.template.yaml')).read()
    s3 = boto3.resource('s3')
    obj = s3.Object(s3_bucket_name, 'empty.template.yaml')
    obj.put(Body=template)
    LOGGER.info('Finished adding empty product template to s3')
    LOGGER.info('Finished bootstrap')

    with betterboto_client.ClientContextManager('codecommit') as codecommit:
        response = codecommit.get_repository(repositoryName=SERVICE_CATALOG_FACTORY_REPO_NAME)
        clone_url = response.get('repositoryMetadata').get('cloneUrlHttp')
        clone_command = "git clone --config 'credential.helper=!aws codecommit " \
                        "credential-helper $@' --config 'credential.UseHttpPath=true' " \
                        "{}".format(clone_url)
        click.echo(
            'You need to clone your newly created repo and then seed it: \n{}'.format(
                clone_command
            )
        )


@cli.command()
@click.argument('complexity', default='simple')
@click.argument('p', type=click.Path(exists=True))
def seed(complexity, p):
    target = os.path.sep.join([p, 'portfolios'])
    if not os.path.exists(target):
        os.makedirs(target)

    example = "example-{}.yaml".format(complexity)
    shutil.copy2(
        resolve_from_site_packages(
            os.path.sep.join(['portfolios', example])
        ),
        os.path.sep.join([target, example])
    )


@cli.command()
@click.argument('p', type=click.Path(exists=True))
def reseed(p):
    for f in ['requirements.txt', 'cli.py']:
        shutil.copy2(
            resolve_from_site_packages(f),
            os.path.sep.join([p, f])
        )
    for d in ['templates']:
        target = os.path.sep.join([p, d])
        if os.path.exists(target):
            shutil.rmtree(target)
        shutil.copytree(
            resolve_from_site_packages(d),
            target
        )


@cli.command()
def version():
    click.echo("cli version: {}".format(VERSION))
    with betterboto_client.ClientContextManager('ssm', region_name=HOME_REGION) as ssm:
        response = ssm.get_parameter(
            Name="service-catalog-factory-regional-version"
        )
        click.echo(
            "regional stack version: {} for region: {}".format(
                response.get('Parameter').get('Value'),
                response.get('Parameter').get('ARN').split(':')[3]
            )
        )
        response = ssm.get_parameter(
            Name="service-catalog-factory-version"
        )
        click.echo(
            "stack version: {}".format(
                response.get('Parameter').get('Value'),
            )
        )


@cli.command()
@click.argument('p', type=click.Path(exists=True))
def upload_config(p):
    do_upload_config(p)


def do_upload_config(p):
    content = open(p, 'r').read()
    with betterboto_client.ClientContextManager('ssm') as ssm:
        ssm.put_parameter(
            Name=CONFIG_PARAM_NAME,
            Type='String',
            Value=content,
            Overwrite=True,
        )
    click.echo("Uploaded config")


@cli.command()
@click.argument('p', type=click.Path(exists=True))
def fix_issues(p):
    fix_issues_for_portfolio(p)


def fix_issues_for_portfolio(p):
    click.echo('Fixing issues for portfolios')
    for portfolio_file_name in os.listdir(p):
        p_name = portfolio_file_name.split(".")[0]
        with open(os.path.sep.join([p, portfolio_file_name]), 'r') as portfolio_file:
            portfolio = yaml.safe_load(portfolio_file.read())
            for portfolio in portfolio.get('Portfolios', []):
                for component in portfolio.get('Components', []):
                    for version in component.get('Versions', []):
                        stack_name = "-".join([
                            p_name,
                            portfolio.get('DisplayName'),
                            component.get('Name'),
                            version.get('Name'),
                        ])
                        LOGGER.info('looking at stack: {}'.format(stack_name))
                        with betterboto_client.ClientContextManager('cloudformation') as cloudformation:
                            response = {'Stacks': []}
                            try:
                                response = cloudformation.describe_stacks(StackName=stack_name)
                            except cloudformation.exceptions.ClientError as e:
                                if "Stack with id {} does not exist".format(stack_name) in str(e):
                                    click.echo("There is no pipeline for: {}".format(stack_name))
                                else:
                                    raise e

                            for stack in response.get('Stacks'):
                                if stack.get('StackStatus') == "ROLLBACK_COMPLETE":
                                    if click.confirm(
                                            'Found a stack: {} in status: "ROLLBACK_COMPLETE".  '
                                            'Should it be deleted?'.format(stack_name)
                                    ):
                                        cloudformation.delete_stack(StackName=stack_name)
                                        waiter = cloudformation.get_waiter('stack_delete_complete')
                                        waiter.wait(StackName=stack_name)

    click.echo('Finished fixing issues for portfolios')


@cli.command()
@click.argument('stack-name')
def delete_stack_from_all_regions(stack_name):
    all_regions = get_regions()
    if click.confirm(
            "We are going to delete the stack: {} from all regions: {}.  Are you sure?".format(
                stack_name, all_regions
            )
    ):
        threads = []
        for region in all_regions:
            process = Thread(
                name=region,
                target=delete_stack_from_a_regions,
                kwargs={
                    'stack_name': stack_name,
                    'region': region,
                }
            )
            process.start()
            threads.append(process)
        for process in threads:
            process.join()


def delete_stack_from_a_regions(stack_name, region):
    click.echo("Deleting stack: {} from region: {}".format(stack_name, region))
    with betterboto_client.ClientContextManager('cloudformation', region_name=region) as cloudformation:
        cloudformation.delete_stack(StackName=stack_name)
        waiter = cloudformation.get_waiter('stack_delete_complete')
        waiter.wait(StackName=stack_name)
    click.echo("Finished")


@cli.command()
@click.argument('p')
def demo(p, type=click.Path(exists=True)):
    click.echo("Starting demo")
    click.echo("Setting up your config")
    config_yaml = 'config.yaml'
    if os.path.exists(os.path.sep.join([p, config_yaml])):
        click.echo('Using config.yaml')
    else:
        shutil.copy2(
            resolve_from_site_packages(
                'example-config-small.yaml'
            ),
            os.path.sep.join([p, config_yaml])
        )
    do_upload_config(os.path.sep.join([p, config_yaml]))
    click.echo("Finished setting up your config")
    do_bootstrap()
    commit_id_to_wait_for = add_or_update_file_in_branch_for_repo(
        'master',
        'portfolios/demo.yaml',
        read_from_site_packages('portfolios/example-simple.yaml'),
        'ServiceCatalogFactory'
    )
    click.echo('Waiting for the pipeline to finish')
    wait_for_pipeline(commit_id_to_wait_for, 'servicecatalog-factory-pipeline')
    product_name = 'account-iam'
    with betterboto_client.ClientContextManager('codecommit') as codecommit:
        response = codecommit.list_repositories()
        repo_name = product_name
        if repo_name not in [r.get('repositoryName') for r in response.get('repositories', [])]:
            click.echo('Creating {} repository'.format(repo_name))
            codecommit.create_repository(
                repositoryName=repo_name,
            )
        commit_id_to_wait_for = add_or_update_file_in_branch_for_repo(
            'v1',
            'product.template.yaml',
            requests.get(
                'https://raw.githubusercontent.com/eamonnfaherty/cloudformation-templates/master/iam_admin_role/product.template.yaml'
            ).text,
            repo_name
        )
    wait_for_pipeline(commit_id_to_wait_for, 'demo-central-it-team-portfolio-account-iam-v1-pipeline')
    product_created = False
    with betterboto_client.ClientContextManager('servicecatalog') as servicecatalog:
        response = servicecatalog.search_products_as_admin()
        for product_view_detail in response.get('ProductViewDetails', []):
            if product_view_detail.get('ProductViewSummary').get('Name') == product_name:
                product_created = True
                click.echo("Created AWS ServiceCatalog product: {}".format(
                    product_view_detail.get('ProductViewSummary').get('ProductId')
                ))
    assert product_created, 'Product was not created!'
    click.echo("Finished demo")


def add_or_update_file_in_branch_for_repo(branch_name, file_path, contents, repo_name):
    with betterboto_client.ClientContextManager('codecommit') as codecommit:
        response = codecommit.list_branches(repositoryName=repo_name)
        if len(response.get('branches')) == 0:
            click.echo("Adding simple example portfolio")
            response = codecommit.create_commit(
                repositoryName=repo_name,
                branchName=branch_name,
                putFiles=[
                    {
                        'filePath': file_path,
                        'fileMode': 'NORMAL',
                        'fileContent': contents,
                    },
                ],
            )
            commit_id_to_wait_for = response.get('commitId')
        else:
            click.echo("Updating simple example portfolio")
            response = codecommit.get_branch(
                repositoryName=repo_name,
                branchName=branch_name,
            )
            commitId = response.get('branch').get('commitId')
            try:
                response = codecommit.put_file(
                    repositoryName=repo_name,
                    branchName=branch_name,
                    fileContent=contents,
                    parentCommitId=commitId,
                    filePath=file_path,
                    fileMode='NORMAL',
                    commitMessage='adding',
                )
                commit_id_to_wait_for = response.get('commitId')
                click.echo("Finished updating simple example portfolio")
            except codecommit.exceptions.SameFileContentException as e:
                commit_id_to_wait_for = commitId
                click.echo("NO updating was needed to simple example portfolio")
    return commit_id_to_wait_for


def wait_for_pipeline(commit_id_to_wait_for, pipeline_name):
    pipeline_execution = None
    with betterboto_client.ClientContextManager('codepipeline') as codepipeline:
        while pipeline_execution is None:
            click.echo('Looking for pipeline execution')
            time.sleep(1)
            response = codepipeline.list_pipeline_executions(
                pipelineName=pipeline_name
            )
            for pipeline_execution_summary in response.get('pipelineExecutionSummaries', []):
                for source_revision in pipeline_execution_summary.get('sourceRevisions', []):
                    if source_revision.get('revisionId') == commit_id_to_wait_for:
                        pipeline_execution = pipeline_execution_summary
    click.echo("Found pipeline execution")
    pipeline_execution['status'] = 'InProgress'
    while pipeline_execution.get('status') == 'InProgress':
        click.echo("Waiting for execution to complete")
        time.sleep(1)
        response = codepipeline.get_pipeline_execution(
            pipelineName=pipeline_name,
            pipelineExecutionId=pipeline_execution.get('pipelineExecutionId')
        )
        pipeline_execution = response.get('pipelineExecution')
    if pipeline_execution.get('status') == 'Succeeded':
        click.echo("Pipeline finished running")
    else:
        raise Exception('Pipeline failed to run: {}'.format(pipeline_execution))


if __name__ == "__main__":
    cli()
