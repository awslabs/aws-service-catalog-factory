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

OUTPUT = "output"
HASH_PREFIX = 'a'

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
            for version in product.get('Versions', []):
                portfolio_ids_by_region_for_component, product_ids_by_region = generate_pipeline(
                    ENV.get_template(COMPONENT),
                    portfolios_groups_name,
                    output_path,
                    version,
                    product,
                    portfolio,
                )
                portfolio_ids_by_region.update(portfolio_ids_by_region_for_component)
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


def generate_portfolios(portfolios_file_path):
    LOGGER.info('Loading portfolio: {}'.format(portfolios_file_path))
    with open(portfolios_file_path) as portfolios_file:
        portfolio_file_name = portfolios_file_path.split("/")[-1]
        portfolio_file_name = portfolio_file_name.replace(".yaml", "")
        portfolios_file_contents = portfolios_file.read()
        portfolios = yaml.safe_load(portfolios_file_contents)
        LOGGER.info("Checking for external config")
        for portfolio in portfolios.get('Portfolios'):
            for component in portfolio.get('Components'):
                portfolio_external_components_specification_path = os.path.sep.join(
                    [
                        'portfolios',
                        portfolio_file_name,
                        'Portfolios',
                        portfolio.get('DisplayName'),
                        'Components',
                        component.get('Name'),
                        'Versions'
                    ]
                )
                if os.path.exists(portfolio_external_components_specification_path):
                    external_versions = os.listdir(portfolio_external_components_specification_path)
                    for external_version in external_versions:
                        specification = open(
                            os.path.sep.join([
                                portfolio_external_components_specification_path,
                                external_version,
                                'specification.yaml'
                            ]),
                            'r'
                        ).read()
                        version_spec = yaml.safe_load(specification)
                        version_spec['Name'] = external_version
                        if component.get('Versions') is None:
                            component['Versions'] = []
                        LOGGER.info("Adding external version: {} to component: {}".format(
                            version_spec.get('Name'),
                            component.get('Name'),
                        ))
                        component['Versions'].append(version_spec)
        return portfolios


@cli.command()
@click.argument('p', type=click.Path(exists=True))
def generate(p):
    LOGGER.info('Generating')
    for portfolio_file_name in os.listdir(p):
        if '.yaml' in portfolio_file_name:
            p_name = portfolio_file_name.split(".")[0]
            output_path = os.path.sep.join([OUTPUT, p_name])
            portfolios_file_path = os.path.sep.join([p, portfolio_file_name])
            portfolios = generate_portfolios(portfolios_file_path)
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
    do_deploy(p)


def do_deploy(p):
    stacks = get_stacks()
    for portfolio_file_name in os.listdir(p):
        if '.yaml' in portfolio_file_name:
            p_name = portfolio_file_name.split(".")[0]
            output_path = os.path.sep.join([OUTPUT, p_name])
            portfolios_file_path = os.path.sep.join([p, portfolio_file_name])
            portfolios = generate_portfolios(portfolios_file_path)
            for portfolio in portfolios.get('Portfolios'):
                for product in portfolio.get('Components', []):
                    for version in product.get('Versions', []):
                        friendly_uid = "-".join([
                            p_name, portfolio.get('DisplayName'), product.get('Name'), version.get('Name')
                        ])
                        first_run_of_stack = stacks.get(friendly_uid, False) is False
                        LOGGER.info('Running deploy for: {}. Is first run: {}'.format(
                            friendly_uid, first_run_of_stack
                        ))
                        run_deploy_for_component(
                            output_path,
                            friendly_uid,
                        )


def get_hash_for_template(template):
    hasher = hashlib.md5()
    hasher.update(str.encode(template))
    return "{}{}".format(HASH_PREFIX, hasher.hexdigest())


def run_deploy_for_component(path, friendly_uid):
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
    do_bootstrap_branch(branch_name)


def do_bootstrap_branch(branch_name):
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
    do_seed(complexity, p)


def do_seed(complexity, p):
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
def version():
    do_version()


def do_version():
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
    do_fix_issues(p)


def do_fix_issues(p):
    fix_issues_for_portfolio(p)


def fix_issues_for_portfolio(p):
    click.echo('Fixing issues for portfolios')
    for portfolio_file_name in os.listdir(p):
        if '.yaml' in portfolio_file_name:
            p_name = portfolio_file_name.split(".")[0]
            portfolios = generate_portfolios(os.path.sep.join([p, portfolio_file_name]))
            for portfolio in portfolios.get('Portfolios', []):
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
    do_delete_stack_from_all_regions(stack_name)


def do_delete_stack_from_all_regions(stack_name):
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
def quick_start():
    do_quick_start()


def do_quick_start():
    click.echo("Starting demo")
    click.echo("Setting up your config")
    region = os.environ.get("AWS_DEFAULT_REGION")
    content = yaml.safe_dump({
        "regions": [
            'eu-west-1',
            'eu-west-2',
            'eu-west-3'
        ]
    })
    with betterboto_client.ClientContextManager('ssm') as ssm:
        ssm.put_parameter(
            Name=CONFIG_PARAM_NAME,
            Type='String',
            Value=content,
            Overwrite=True,
        )
    click.echo("Finished setting up your config")
    do_bootstrap()

    if os.path.exists('ServiceCatalogFactory') and False:
        click.echo("Found ServiceCatalogFactory so not cloning or seeding")
    else:
        click.echo("Cloning for you")
        command = "git clone " \
                  "--config 'credential.helper=!aws codecommit credential-helper $@' " \
                  "--config 'credential.UseHttpPath=true' " \
                  f"https://git-codecommit.{region}.amazonaws.com/v1/repos/ServiceCatalogFactory"
        os.system(command)
        click.echo("Seeding")
        os.makedirs(
            os.path.sep.join([
                'ServiceCatalogFactory',
                'portfolios'
            ])
        )
        manifest = Template(
            read_from_site_packages(os.path.sep.join(["portfolios", "example-quickstart.yaml"]))
        ).render()
        open(os.path.sep.join(["ServiceCatalogFactory", "portfolios", "demo.yaml"]), 'w').write(
            manifest
        )
        click.echo("Pushing manifest")
        os.system("cd ServiceCatalogFactory && git add . && git commit -am 'initial add' && git push")

        map = {
            'account-vending-account-creation': {
                'owner_and_repo': 'awslabs/aws-service-catalog-factory',
                'branch': 'trunk',
                'directory': 'account-vending/account-creation-product',
            },
            'account-vending-account-bootstrap-shared': {
                'owner_and_repo': 'awslabs/aws-service-catalog-factory',
                'branch': 'trunk',
                'directory': 'account-vending/account-bootstrap-shared-product',
            },
            'account-vending-account-creation-shared': {
                'owner_and_repo': 'awslabs/aws-service-catalog-factory',
                'branch': 'trunk',
                'directory': 'account-vending/account-creation-shared-product',
            },
        }

        for product_name in [
            'account-vending-account-creation',
            'account-vending-account-bootstrap-shared',
            'account-vending-account-creation-shared',
        ]:
            os.system(f'aws codecommit create-repository --repository-name {product_name}')
            command = "git clone " \
                      "--config 'credential.helper=!aws codecommit credential-helper $@' " \
                      "--config 'credential.UseHttpPath=true' " \
                      f"https://git-codecommit.{region}.amazonaws.com/v1/repos/{product_name}"
            os.system(command)
            source = "https://github.com/{owner_and_repo}/{branch}/{directory}".format(**map.get(product_name))
            os.system(f"svn export {source} {product_name} --force")
            os.system(f"cd {product_name} && git add . && git commit -am 'initial add' && git push")

    click.echo("All done!")


if __name__ == "__main__":
    cli()
