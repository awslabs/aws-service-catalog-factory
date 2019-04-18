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
    for porfolio_file_name in os.listdir(p):
        p_name = porfolio_file_name.split(".")[0]
        output_path = os.path.sep.join(["output", p_name])
        portfolios_file_path = os.path.sep.join([p, porfolio_file_name])
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
@click.argument('portfolio-group')
@click.argument('portfolio-display-name')
@click.argument('product')
@click.argument('version')
def nuke_product_version(portfolio_group, portfolio_display_name, product, version):
    LOGGER.info('Looking for portfolio_id')
    with betterboto_client.ClientContextManager('servicecatalog') as servicecatalog:
        response = servicecatalog.list_portfolios(PageSize=20)
        assert response.get('NextPageToken', None) is None, "Pagination not supported"
        portfolio_id = None
        portfolio_name = "-".join([portfolio_group, portfolio_display_name])
        for portfolio_detail in response.get('PortfolioDetails'):
            if portfolio_detail.get('DisplayName') == portfolio_name:
                portfolio_id = portfolio_detail.get('Id')
                break
        if portfolio_id is None:
            LOGGER.warning("Portfolio {} could not be found".format(portfolio_id))
        else:
            LOGGER.info('Portfolio_id found: {}'.format(portfolio_id))
            product_name = "-".join([product, version])
            LOGGER.info('Looking for product: {}'.format(product_name))
            result = product_exists(servicecatalog, {'Name': product}, PortfolioId=portfolio_id)
            product_id = result.get('ProductId')
            LOGGER.info('Looking for version: {}'.format(version))
            response = servicecatalog.list_provisioning_artifacts(
                ProductId=product_id,
            )
            assert response.get('NextPageToken', None) is None, "Pagination not supported"
            version_id = None
            for provisioning_artifact_detail in response.get('ProvisioningArtifactDetails'):
                if provisioning_artifact_detail.get('Name') == version:
                    version_id = provisioning_artifact_detail.get('Id')
            if version_id is None:
                LOGGER.warning("Version {} could not be found".format(version))
            else:
                LOGGER.info('Found version: {}'.format(version_id))
                LOGGER.info('Deleting version: {}'.format(version_id))
                servicecatalog.delete_provisioning_artifact(
                    ProductId=product_id,
                    ProvisioningArtifactId=version_id
                )
                LOGGER.info('Deleted version: {}'.format(version_id))

        LOGGER.info('Starting to delete pipeline stack')
        with betterboto_client.ClientContextManager('cloudformation') as cloudformation:
            stack_name = "-".join([portfolio_group, portfolio_display_name, product, version])
            LOGGER.info('Emptying the pipeline bucket first')
            response = cloudformation.list_stack_resources(
                StackName=stack_name
            )
            assert response.get('NextPageToken', None) is None, "Pagination not supported"
            bucket_name = None
            for stack_resource_summary in response.get('StackResourceSummaries'):
                if stack_resource_summary.get("LogicalResourceId") == "PipelineArtifactBucket":
                    bucket_name = stack_resource_summary.get('PhysicalResourceId')
                    break
            assert bucket_name is not None, "Could not find bucket for the pipeline"
            s3 = boto3.resource('s3')
            bucket = s3.Bucket(bucket_name)
            bucket.objects.all().delete()
            LOGGER.info('Finished emptying the pipeline bucket')

            LOGGER.info('Deleting the stack {}'.format(stack_name))
            cloudformation.delete_stack(
                StackName=stack_name
            )
            waiter = cloudformation.get_waiter('stack_delete_complete')
            waiter.wait(StackName=stack_name)
            LOGGER.info('Finished deleting pipeline stack')


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
    click.echo(VERSION)


@cli.command()
@click.argument('p', type=click.Path(exists=True))
def upload_config(p):
    content = open(p, 'r').read()
    with betterboto_client.ClientContextManager('ssm') as ssm:
        ssm.put_parameter(
            Name=CONFIG_PARAM_NAME,
            Type='String',
            Value=content,
            Overwrite=True,
        )
    click.echo("Uploaded config")


if __name__ == "__main__":
    cli()
