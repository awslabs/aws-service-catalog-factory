# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import hashlib
import json
import logging
import os
from glob import glob

import cfn_tools
import colorclass
import terminaltables
from pathlib import Path

import boto3
import click
import luigi
import yaml
from jinja2 import Environment, FileSystemLoader, Template
from pykwalify.core import Core
import collections
from copy import deepcopy
from betterboto import client as betterboto_client
from threading import Thread
import shutil

from . import constants
from . import aws
from . import luigi_tasks_and_targets

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)


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
    with betterboto_client.ClientContextManager('ssm', region_name=constants.HOME_REGION) as ssm:
        response = ssm.get_parameter(Name=constants.CONFIG_PARAM_NAME)
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


def get_bucket_name():
    s3_bucket_url = None
    with betterboto_client.ClientContextManager(
            'cloudformation', region_name=constants.HOME_REGION
    ) as cloudformation:
        response = cloudformation.describe_stacks(
            StackName=constants.BOOTSTRAP_STACK_NAME
        )
        assert len(response.get('Stacks')) == 1, "There should only be one stack with the name"
        outputs = response.get('Stacks')[0].get('Outputs')
        for output in outputs:
            if output.get('OutputKey') == "CatalogBucketName":
                s3_bucket_url = output.get('OutputValue')
        assert s3_bucket_url is not None, "Could not find bucket"
        return s3_bucket_url


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
            check_for_external_definitions_for(portfolio, portfolio_file_name, 'Components')
            check_for_external_definitions_for(portfolio, portfolio_file_name, 'Products')
        return portfolios


def check_for_external_definitions_for(portfolio, portfolio_file_name, type):
    for component in portfolio.get(type, []):
        portfolio_external_components_specification_path = os.path.sep.join(
            [
                'portfolios',
                portfolio_file_name,
                'Portfolios',
                portfolio.get('DisplayName'),
                type,
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
                LOGGER.info(f"Adding external version: {version_spec.get('Name')} to {type}: {component.get('Name')}")
                component['Versions'].append(version_spec)


@cli.command()
@click.argument('p', type=click.Path(exists=True))
def generate_via_luigi(p):
    LOGGER.info('Generating')
    all_tasks = {}
    all_regions = get_regions()
    products_by_region = {}
    version_pipelines_to_build = []

    for portfolio_file_name in os.listdir(p):
        if '.yaml' in portfolio_file_name:
            p_name = portfolio_file_name.split(".")[0]
            output_path = os.path.sep.join([constants.OUTPUT, p_name])
            portfolios_file_path = os.path.sep.join([p, portfolio_file_name])
            portfolios = generate_portfolios(portfolios_file_path)
            for region in all_regions:
                for portfolio in portfolios.get('Portfolios', []):
                    create_portfolio_task_args = {
                        "region": region,
                        "portfolio_group_name": p_name,
                        "display_name": portfolio.get('DisplayName'),
                        "description": portfolio.get('Description'),
                        "provider_name": portfolio.get('ProviderName'),
                        "associations": portfolio.get('Associations'),
                        "tags": portfolio.get('Tags'),
                    }
                    create_portfolio_task = luigi_tasks_and_targets.CreatePortfolioTask(
                        **create_portfolio_task_args
                    )
                    all_tasks[f"portfolio_{p_name}_{portfolio.get('DisplayName')}-{region}"] = create_portfolio_task
                    nested_products = portfolio.get('Products', []) + portfolio.get('Components', [])
                    for product in nested_products:
                        product_uid = f"{product.get('Name')}"
                        if products_by_region.get(product_uid) is None:
                            products_by_region[product_uid] = {}

                        create_product_task_args = {
                            "region": region,
                            "name": product.get('Name'),
                            "owner": product.get('Owner'),
                            "description": product.get('Description'),
                            "distributor": product.get('Distributor'),
                            "support_description": product.get('SupportDescription'),
                            "support_email": product.get('SupportEmail'),
                            "support_url": product.get('SupportUrl'),
                            "tags": product.get('Tags'),
                            "uid": "-".join([
                                create_portfolio_task_args.get('portfolio_group_name'),
                                create_portfolio_task_args.get('display_name'),
                                product.get('Name'),
                            ])
                        }
                        products_by_region[product_uid][region] = create_product_task_args

                        create_product_task = luigi_tasks_and_targets.CreateProductTask(
                            **create_product_task_args
                        )
                        all_tasks[
                            f"product_{p_name}_{portfolio.get('DisplayName')}_{product.get('Name')}-{region}"
                        ] = create_product_task

                        associate_product_with_portfolio_task = luigi_tasks_and_targets.AssociateProductWithPortfolioTask(
                            region=region,
                            portfolio_args=create_portfolio_task_args,
                            product_args=create_product_task_args,
                        )
                        all_tasks[
                            f"association_{p_name}_{portfolio.get('DisplayName')}_{product.get('Name')}-{region}"
                        ] = associate_product_with_portfolio_task
                        for version in product.get('Versions', []):
                            ensure_product_version_details_correct_task = luigi_tasks_and_targets.EnsureProductVersionDetailsCorrect(
                                region=region,
                                version=version,
                                product_args=create_product_task_args,
                            )
                            version_pipelines_to_build.append({
                                'create_product_task_args': create_product_task_args,
                                'product':product,
                                'version':version,
                            })
                            all_tasks[
                                f"version_{p_name}_{portfolio.get('Name')}_{product.get('Name')}_{version.get('Name')}-{region}"
                            ] = ensure_product_version_details_correct_task
                for product in portfolios.get('Products', []):
                    product_uid = f"{product.get('Name')}"
                    if products_by_region.get(product_uid) is None:
                        products_by_region[product_uid] = {}
                    create_product_task_args = {
                        "region": region,
                        "name": product.get('Name'),
                        "owner": product.get('Owner'),
                        "description": product.get('Description'),
                        "distributor": product.get('Distributor'),
                        "support_description": product.get('SupportDescription'),
                        "support_email": product.get('SupportEmail'),
                        "support_url": product.get('SupportUrl'),
                        "tags": product.get('Tags'),
                        "uid": product.get('Name'),
                    }
                    products_by_region[product_uid][region] = create_product_task_args
                    create_product_task = luigi_tasks_and_targets.CreateProductTask(
                        **create_product_task_args
                    )

                    for portfolio in product.get('Portfolios', []):
                        create_portfolio_task_args = all_tasks[f"portfolio_{p_name}_{portfolio}-{region}"].param_kwargs
                        associate_product_with_portfolio_task = luigi_tasks_and_targets.AssociateProductWithPortfolioTask(
                            region=region,
                            portfolio_args=create_portfolio_task_args,
                            product_args=create_product_task_args,
                        )
                        all_tasks[
                            f"association_{portfolio}_{product.get('Name')}-{region}"
                        ] = associate_product_with_portfolio_task

                    for version in product.get('Versions', []):
                        version_pipelines_to_build.append({
                            'create_product_task_args': create_product_task_args,
                            'product': product,
                            'version': version,
                        })
                        ensure_product_version_details_correct_task = luigi_tasks_and_targets.EnsureProductVersionDetailsCorrect(
                                region=region,
                                version=version,
                                product_args=create_product_task_args,
                        )
                        all_tasks[
                            f"version_{product.get('Name')}_{version.get('Name')}-{region}"
                        ] = ensure_product_version_details_correct_task

                    all_tasks[f"product_{p_name}-{region}"] = create_product_task

    LOGGER.info("Going to create pipeline tasks")
    for version_pipeline_to_build in version_pipelines_to_build:
        product_name = version_pipeline_to_build.get('product').get('Name')
        create_args = {
            "all_regions": all_regions,
            "version": version_pipeline_to_build.get('version'),
            "product": version_pipeline_to_build.get('product'),
            "products_args_by_region": products_by_region.get(product_name),
        }
        t = luigi_tasks_and_targets.CreateVersionPipelineTemplateTask(
            **create_args
        )
        LOGGER.info(f"created pipeline_template_{product_name}-{version_pipeline_to_build.get('version').get('Name')}")
        all_tasks[f"pipeline_template_{product_name}-{version_pipeline_to_build.get('version').get('Name')}"] = t

        t = luigi_tasks_and_targets.CreateVersionPipelineTask(
            **create_args
        )
        LOGGER.info(f"created pipeline_{product_name}-{version_pipeline_to_build.get('version').get('Name')}")
        all_tasks[f"pipeline_{product_name}-{version_pipeline_to_build.get('version').get('Name')}"] = t

    for type in ["failure", "success", "timeout", "process_failure", "processing_time", "broken_task", ]:
        os.makedirs(Path(constants.RESULTS_DIRECTORY) / type)

    run_result = luigi.build(
        all_tasks.values(),
        local_scheduler=True,
        detailed_summary=True,
        workers=10,
        log_level='INFO',
    )

    table_data = [
        ['Result', 'Task', 'Significant Parameters', 'Duration'],

    ]
    table = terminaltables.SingleTable(table_data)
    for filename in glob('results/processing_time/*.json'):
        result = json.loads(open(filename, 'r').read())
        table_data.append([
            colorclass.Color("{green}Success{/green}"),
            result.get('task_type'),
            yaml.safe_dump(result.get('params_for_results')),
            result.get('duration'),
        ])
    click.echo(table.table)

    for filename in glob('results/failure/*.json'):
        result = json.loads(open(filename, 'r').read())
        click.echo(colorclass.Color("{red}"+result.get('task_type')+" failed{/red}"))
        click.echo(f"{yaml.safe_dump({'parameters':result.get('task_params')})}")
        click.echo("\n".join(result.get('exception_stack_trace')))
        click.echo('')


@cli.command()
@click.argument('p', type=click.Path(exists=True))
def show_pipelines(p):
    pipeline_names = [f"{constants.BOOTSTRAP_STACK_NAME}-pipeline"]
    for portfolio_file_name in os.listdir(p):
        if '.yaml' in portfolio_file_name:
            p_name = portfolio_file_name.split(".")[0]
            portfolios_file_path = os.path.sep.join([p, portfolio_file_name])
            portfolios = generate_portfolios(portfolios_file_path)

            for portfolio in portfolios.get('Portfolios', []):
                nested_products = portfolio.get('Products', []) + portfolio.get('Components', [])
                for product in nested_products:
                    for version in product.get('Versions', []):
                        pipeline_names.append(
                            f"{p_name}-{portfolio.get('DisplayName')}-{product.get('Name')}-{version.get('Name')}-pipeline"
                        )
            for product in portfolios.get('Products', []):
                for version in product.get('Versions', []):
                    pipeline_names.append(
                        f"{product.get('Name')}-{version.get('Name')}-pipeline"
                    )
    table_data = [
        ['Pipeline', 'Status', 'Last Commit Hash', 'Last Commit Message'],
    ]
    for pipeline_name in pipeline_names:
        result = aws.get_details_for_pipeline(pipeline_name)
        status = result.get('status')
        if status == "Succeeded":
            status = "{green}" + status + "{/green}"
        elif status == "Failed":
            status = "{red}" + status + "{/red}"
        else:
            status = "{yellow}" + status + "{/yellow}"
        if len(result.get('sourceRevisions')) > 0:
            revision = result.get('sourceRevisions')[0]
        else:
            revision = {
                'revisionId': 'N/A',
                'revisionSummary': 'N/A',
            }
        table_data.append([
            pipeline_name,
            colorclass.Color(status),
            revision.get('revisionId'),
            revision.get('revisionSummary').strip(),
        ])

    table = terminaltables.SingleTable(table_data)
    click.echo(table.table)


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
            output_path = os.path.sep.join([constants.OUTPUT, p_name])
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
    return "{}{}".format(constants.HASH_PREFIX, hasher.hexdigest())


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
            result = aws.get_product(servicecatalog, product)
            if result is not None:
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
    constants.VERSION = "https://github.com/awslabs/aws-service-catalog-factory/archive/{}.zip".format(branch_name)
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
        LOGGER.info('Creating {}-regional'.format(constants.BOOTSTRAP_STACK_NAME))
        threads = []
        template = read_from_site_packages(
            '{}.template.yaml'.format('{}-regional'.format(constants.BOOTSTRAP_STACK_NAME))
        )
        template = Template(template).render(VERSION=constants.VERSION)
        args = {
            'StackName': '{}-regional'.format(constants.BOOTSTRAP_STACK_NAME),
            'TemplateBody': template,
            'Capabilities': ['CAPABILITY_IAM'],
            'Parameters': [
                {
                    'ParameterKey': 'Version',
                    'ParameterValue': constants.VERSION,
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
        LOGGER.info('Finished creating {}-regional'.format(constants.BOOTSTRAP_STACK_NAME))
    click.echo('Completed regional deployments')

    click.echo('Starting main deployment')
    s3_bucket_name = None
    with betterboto_client.ClientContextManager('cloudformation') as cloudformation:
        LOGGER.info('Creating {}'.format(constants.BOOTSTRAP_STACK_NAME))
        template = read_from_site_packages('{}.template.yaml'.format(constants.BOOTSTRAP_STACK_NAME))
        template = Template(template).render(VERSION=constants.VERSION)
        args = {
            'StackName': constants.BOOTSTRAP_STACK_NAME,
            'TemplateBody': template,
            'Capabilities': ['CAPABILITY_NAMED_IAM'],
            'Parameters': [
                {
                    'ParameterKey': 'Version',
                    'ParameterValue': constants.VERSION,
                    'UsePreviousValue': False,
                },
            ],
        }
        cloudformation.create_or_update(**args)
        response = cloudformation.describe_stacks(StackName=constants.BOOTSTRAP_STACK_NAME)
        assert len(response.get('Stacks')) == 1, "Error code 1"
        stack_outputs = response.get('Stacks')[0]['Outputs']
        for stack_output in stack_outputs:
            if stack_output.get('OutputKey') == 'CatalogBucketName':
                s3_bucket_name = stack_output.get('OutputValue')
                break
        LOGGER.info(
            'Finished creating {}. CatalogBucketName is: {}'.format(
                constants.BOOTSTRAP_STACK_NAME, s3_bucket_name
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
        response = codecommit.get_repository(repositoryName=constants.SERVICE_CATALOG_FACTORY_REPO_NAME)
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
    click.echo("cli version: {}".format(constants.VERSION))
    with betterboto_client.ClientContextManager('ssm', region_name=constants.HOME_REGION) as ssm:
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
            Name=constants.CONFIG_PARAM_NAME,
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
            Name=constants.CONFIG_PARAM_NAME,
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


@cli.command()
def list_resources():
    click.echo("# Framework resources")

    click.echo("## SSM Parameters used")
    click.echo(f"- {constants.CONFIG_PARAM_NAME}")

    for file in Path(__file__).parent.resolve().glob("*.template.yaml"):
        if 'empty.template.yaml' == file.name:
            continue
        template_contents = Template(open(file, 'r').read()).render()
        template = cfn_tools.load_yaml(template_contents)
        click.echo(f"## Resources for stack: {file.name.split('.')[0]}")
        table_data = [
            ['Logical Name', 'Resource Type', 'Name', ],
        ]
        table = terminaltables.SingleTable(table_data)
        for logical_name, resource in template.get('Resources').items():
            resource_type = resource.get('Type')

            name = '-'

            type_to_name = {
                'AWS::IAM::Role': 'RoleName',
                'AWS::SSM::Parameter': 'Name',
                'AWS::S3::Bucket': 'BucketName',
                'AWS::CodePipeline::Pipeline': 'Name',
                'AWS::CodeBuild::Project': 'Name',
                'AWS::CodeCommit::Repository': 'RepositoryName',
            }

            if type_to_name.get(resource_type) is not None:
                name = resource.get('Properties', {}).get(type_to_name.get(resource_type), 'Not Specified')
                if not isinstance(name, str):
                    name = cfn_tools.dump_yaml(name)

            table_data.append([logical_name, resource_type, name])

        click.echo(table.table)
    click.echo(f"n.b. AWS::StackName evaluates to {constants.BOOTSTRAP_STACK_NAME}")


if __name__ == "__main__":
    cli()
