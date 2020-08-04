# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import hashlib
import json
import logging
import os
import time

import sys
from glob import glob

import cfn_tools
import colorclass
import requests
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
from datetime import datetime
from luigi import LuigiStatusCode

from . import utils
from . import constants
from . import aws
from . import luigi_tasks_and_targets
from . import config

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def resolve_from_site_packages(what):
    return os.path.sep.join([os.path.dirname(os.path.abspath(__file__)), what])


def read_from_site_packages(what):
    return open(resolve_from_site_packages(what), "r").read()


TEMPLATE_DIR = resolve_from_site_packages("templates")
ENV = Environment(loader=FileSystemLoader(TEMPLATE_DIR), extensions=["jinja2.ext.do"],)


def get_regions():
    with betterboto_client.ClientContextManager(
        "ssm", region_name=constants.HOME_REGION
    ) as ssm:
        response = ssm.get_parameter(Name=constants.CONFIG_PARAM_NAME)
        config = yaml.safe_load(response.get("Parameter").get("Value"))
        return config.get("regions")


def merge(dict1, dict2):
    result = deepcopy(dict1)
    for key, value in dict2.items():
        if isinstance(value, collections.Mapping):
            result[key] = merge(result.get(key, {}), value)
        else:
            result[key] = deepcopy(dict2[key])
    return result


def validate(p):
    for portfolio_file_name in os.listdir(p):
        portfolios_file_path = os.path.sep.join([p, portfolio_file_name])
        logger.info("Validating {}".format(portfolios_file_path))
        core = Core(
            source_file=portfolios_file_path,
            schema_files=[resolve_from_site_packages("schema.yaml")],
        )
        core.validate(raise_exception=True)
        click.echo("Finished validating: {}".format(portfolios_file_path))
    click.echo("Finished validating: OK")


def generate_portfolios(portfolios_file_path):
    logger.info("Loading portfolio: {}".format(portfolios_file_path))
    with open(portfolios_file_path) as portfolios_file:
        portfolio_file_name = portfolios_file_path.split("/")[-1]
        portfolio_file_name = portfolio_file_name.replace(".yaml", "")
        portfolios_file_contents = portfolios_file.read()
        portfolios = yaml.safe_load(portfolios_file_contents)
        logger.info("Checking for external config")
        for portfolio in portfolios.get("Portfolios", []):
            check_for_external_definitions_for(
                portfolio, portfolio_file_name, "Components"
            )
            check_for_external_definitions_for(
                portfolio, portfolio_file_name, "Products"
            )
        return portfolios


def check_for_external_definitions_for(portfolio, portfolio_file_name, type):
    for component in portfolio.get(type, []):
        portfolio_external_components_specification_path = os.path.sep.join(
            [
                "portfolios",
                portfolio_file_name,
                "Portfolios",
                portfolio.get("DisplayName"),
                type,
                component.get("Name"),
                "Versions",
            ]
        )
        if os.path.exists(portfolio_external_components_specification_path):
            external_versions = os.listdir(
                portfolio_external_components_specification_path
            )
            for external_version in external_versions:
                specification = open(
                    os.path.sep.join(
                        [
                            portfolio_external_components_specification_path,
                            external_version,
                            "specification.yaml",
                        ]
                    ),
                    "r",
                ).read()
                version_spec = yaml.safe_load(specification)
                version_spec["Name"] = external_version
                if component.get("Versions") is None:
                    component["Versions"] = []
                logger.info(
                    f"Adding external version: {version_spec.get('Name')} to {type}: {component.get('Name')}"
                )
                component["Versions"].append(version_spec)


def generate_via_luigi(p, branch_override=None):
    factory_version = (
        constants.VERSION
        if branch_override is None
        else "https://github.com/awslabs/aws-service-catalog-factory/archive/{}.zip".format(
            branch_override
        )
    )
    logger.info("Generating")
    all_tasks = {}
    all_regions = get_regions()
    products_by_region = {}
    pipeline_versions = list()
    products_versions = dict()

    for portfolio_file_name in os.listdir(p):
        if ".yaml" in portfolio_file_name:
            p_name = portfolio_file_name.split(".")[0]
            portfolios_file_path = os.path.sep.join([p, portfolio_file_name])
            portfolios = generate_portfolios(portfolios_file_path)
            for region in all_regions:
                generate_for_portfolios(
                    all_tasks,
                    factory_version,
                    p_name,
                    portfolios,
                    products_by_region,
                    region,
                    pipeline_versions,
                )
                generate_for_products(
                    all_tasks,
                    p_name,
                    portfolios,
                    products_by_region,
                    region,
                    products_versions,
                )

    logger.info("Going to create pipeline tasks")
    generate_for_portfolios_versions(
        all_regions, all_tasks, factory_version, pipeline_versions, products_by_region,
    )
    generate_for_products_versions(
        all_regions, all_tasks, factory_version, products_versions, products_by_region,
    )

    for type in [
        "failure",
        "success",
        "timeout",
        "process_failure",
        "processing_time",
        "broken_task",
    ]:
        os.makedirs(Path(constants.RESULTS_DIRECTORY) / type)

    run_result = luigi.build(
        all_tasks.values(),
        local_scheduler=True,
        detailed_summary=True,
        workers=10,
        log_level="INFO",
    )

    exit_status_codes = {
        LuigiStatusCode.SUCCESS: 0,
        LuigiStatusCode.SUCCESS_WITH_RETRY: 0,
        LuigiStatusCode.FAILED: 1,
        LuigiStatusCode.FAILED_AND_SCHEDULING_FAILED: 2,
        LuigiStatusCode.SCHEDULING_FAILED: 3,
        LuigiStatusCode.NOT_RUN: 4,
        LuigiStatusCode.MISSING_EXT: 5,
    }

    table_data = [
        ["Result", "Task", "Significant Parameters", "Duration"],
    ]
    table = terminaltables.AsciiTable(table_data)
    for filename in glob("results/processing_time/*.json"):
        result = json.loads(open(filename, "r").read())
        table_data.append(
            [
                colorclass.Color("{green}Success{/green}"),
                result.get("task_type"),
                yaml.safe_dump(result.get("params_for_results")),
                result.get("duration"),
            ]
        )
    click.echo(table.table)

    for filename in glob("results/failure/*.json"):
        result = json.loads(open(filename, "r").read())
        click.echo(
            colorclass.Color("{red}" + result.get("task_type") + " failed{/red}")
        )
        click.echo(f"{yaml.safe_dump({'parameters': result.get('task_params')})}")
        click.echo("\n".join(result.get("exception_stack_trace")))
        click.echo("")

    sys.exit(exit_status_codes.get(run_result.status))


def generate_for_portfolios_versions(
    all_regions, all_tasks, factory_version, pipeline_versions, products_by_region,
):
    for version_pipeline_to_build in pipeline_versions:
        version_details = version_pipeline_to_build.get("version")

        if version_details.get("Status", "active") == "terminated":
            product_name = version_pipeline_to_build.get("product").get("Name")

            for region, product_args in products_by_region.get(product_name).items():
                task_id = f"pipeline_template_{product_name}-{version_details.get('Name')}-{region}"
                all_tasks[task_id] = luigi_tasks_and_targets.DeleteAVersionTask(
                    product_args=product_args, version=version_details.get("Name"),
                )

        else:
            product_name = version_pipeline_to_build.get("product").get("Name")
            tags = {}
            for tag in version_pipeline_to_build.get("product").get("Tags", []):
                tags[tag.get("Key")] = tag.get("Value")

            for tag in version_details.get("Tags", []):
                tags[tag.get("Key")] = tag.get("Value")
            tag_list = []
            for tag_name, value in tags.items():
                tag_list.append({"Key": tag_name, "Value": value})

            create_args = {
                "all_regions": all_regions,
                "version": version_details,
                "product": version_pipeline_to_build.get("product"),
                "provisioner": version_details.get(
                    "Provisioner", {"Type": "CloudFormation"}
                ),
                "products_args_by_region": products_by_region.get(product_name),
                "factory_version": factory_version,
                "tags": tag_list,
            }
            t = luigi_tasks_and_targets.CreateVersionPipelineTemplateTask(**create_args)
            logger.info(
                f"created pipeline_template_{product_name}-{version_details.get('Name')}"
            )
            all_tasks[
                f"pipeline_template_{product_name}-{version_details.get('Name')}"
            ] = t

            t = luigi_tasks_and_targets.CreateVersionPipelineTask(
                **create_args, region=constants.HOME_REGION,
            )
            logger.info(
                f"created pipeline_{product_name}-{version_details.get('Name')}"
            )
            all_tasks[f"pipeline_{product_name}-{version_details.get('Name')}"] = t


def generate_for_products_versions(
    all_regions, all_tasks, factory_version, products_versions, products_by_region,
):

    for product_name, pipeline_details in products_versions.items():

        for version in pipeline_details:
            product = version.get("product")
            pipeline_mode = product.get("PipelineMode", constants.PIPELINE_MODE_DEFAULT)

            if pipeline_mode == constants.PIPELINE_MODE_SPILT:
                generate_for_portfolios_versions(
                    all_regions,
                    all_tasks,
                    factory_version,
                    pipeline_details,
                    products_by_region,
                )
            elif pipeline_mode == constants.PIPELINE_MODE_COMBINED:
                version_status = version.get("version").get(
                    "Status", constants.STATUS_DEFAULT
                )
                if version_status == constants.STATUS_TERMINATED:
                    for region, product_args in products_by_region.get(
                        product_name
                    ).items():
                        task_id = f"pipeline_template_{product_name}-{version.get('version').get('Name')}-{region}"
                        all_tasks[task_id] = luigi_tasks_and_targets.DeleteAVersionTask(
                            product_args=product_args,
                            version=version.get("version").get("Name"),
                        )
                else:
                    task_id = f"pipeline_template_{product_name}_combined"
                    all_tasks[
                        task_id
                    ] = luigi_tasks_and_targets.CreateCombinedProductPipelineTask(
                        all_regions=all_regions,
                        product=product,
                        products_args_by_region=products_by_region.get(product_name),
                        factory_version=factory_version,
                    )
            else:
                raise Exception(f"Invalid PipelineMode: {pipeline_mode}")


def generate_for_products(
    all_tasks, p_name, portfolios, products_by_region, region, products_versions: dict,
):
    for product in portfolios.get("Products", []):
        product_uid = f"{product.get('Name')}"

        if product.get("Status", None) == "terminated":
            all_tasks[
                f"delete_product_{p_name}_{product.get('Name')}-{region}"
            ] = luigi_tasks_and_targets.DeleteProductTask(
                region=region,
                name=product.get("Name"),
                uid=product.get("Name"),
                pipeline_mode=product.get(
                    "PipelineMode", constants.PIPELINE_MODE_SPILT
                ),
            )
            continue

        if products_by_region.get(product_uid) is None:
            products_by_region[product_uid] = {}
        create_product_task_args = {
            "region": region,
            "name": product.get("Name"),
            "owner": product.get("Owner"),
            "description": product.get("Description"),
            "distributor": product.get("Distributor"),
            "support_description": product.get("SupportDescription"),
            "support_email": product.get("SupportEmail"),
            "support_url": product.get("SupportUrl"),
            "tags": product.get("Tags", []),
            "uid": product.get("Name"),
        }
        products_by_region[product_uid][region] = create_product_task_args
        create_product_task = luigi_tasks_and_targets.CreateProductTask(
            **create_product_task_args
        )

        for portfolio in product.get("Portfolios", []):
            create_portfolio_task_args = all_tasks[
                f"portfolio_{p_name}_{portfolio}-{region}"
            ].param_kwargs
            associate_product_with_portfolio_task = luigi_tasks_and_targets.AssociateProductWithPortfolioTask(
                region=region,
                portfolio_args=create_portfolio_task_args,
                product_args=create_product_task_args,
            )
            all_tasks[
                f"association_{portfolio}_{product.get('Name')}-{region}"
            ] = associate_product_with_portfolio_task

        if products_versions.get(product.get("Name")) is None:
            products_versions[product.get("Name")] = list()

        for version in product.get("Versions", []):
            products_versions[product.get("Name")].append(
                {
                    "create_product_task_args": create_product_task_args,
                    "product": product,
                    "version": version,
                }
            )
            ensure_product_version_details_correct_task = luigi_tasks_and_targets.EnsureProductVersionDetailsCorrect(
                region=region, version=version, product_args=create_product_task_args,
            )
            all_tasks[
                f"version_{product.get('Name')}_{version.get('Name')}-{region}"
            ] = ensure_product_version_details_correct_task

        all_tasks[f"product_{p_name}-{region}"] = create_product_task


def generate_for_portfolios(
    all_tasks,
    factory_version,
    p_name,
    portfolios,
    products_by_region,
    region,
    pipeline_versions,
):
    for portfolio in portfolios.get("Portfolios", []):
        create_portfolio_task_args = {
            "region": region,
            "portfolio_group_name": p_name,
            "display_name": portfolio.get("DisplayName"),
            "description": portfolio.get("Description"),
            "provider_name": portfolio.get("ProviderName"),
            "tags": portfolio.get("Tags", []),
        }
        create_portfolio_task = luigi_tasks_and_targets.CreatePortfolioTask(
            **create_portfolio_task_args
        )
        all_tasks[
            f"portfolio_{p_name}_{portfolio.get('DisplayName')}-{region}"
        ] = create_portfolio_task
        create_portfolio_association_task = luigi_tasks_and_targets.CreatePortfolioAssociationTask(
            **create_portfolio_task_args,
            associations=portfolio.get("Associations", []),
            factory_version=factory_version,
        )
        all_tasks[
            f"portfolio_associations_{p_name}_{portfolio.get('DisplayName')}-{region}"
        ] = create_portfolio_association_task
        nested_products = portfolio.get("Products", []) + portfolio.get(
            "Components", []
        )
        for product in nested_products:
            product_uid = f"{product.get('Name')}"

            if product.get("Status", None) == "terminated":
                delete_product_task = luigi_tasks_and_targets.DeleteProductTask(
                    region=region,
                    name=product.get("Name"),
                    uid="-".join(
                        [
                            create_portfolio_task_args.get("portfolio_group_name"),
                            create_portfolio_task_args.get("display_name"),
                            product.get("Name"),
                        ]
                    ),
                    pipeline_mode=constants.PIPELINE_MODE_SPILT,
                )
                all_tasks[
                    f"delete_product_{p_name}_{portfolio.get('DisplayName')}_{product.get('Name')}-{region}"
                ] = delete_product_task
                continue

            if products_by_region.get(product_uid) is None:
                products_by_region[product_uid] = {}

            create_product_task_args = {
                "region": region,
                "name": product.get("Name"),
                "owner": product.get("Owner"),
                "description": product.get("Description"),
                "distributor": product.get("Distributor"),
                "support_description": product.get("SupportDescription"),
                "support_email": product.get("SupportEmail"),
                "support_url": product.get("SupportUrl"),
                "tags": product.get("Tags", []),
                "uid": "-".join(
                    [
                        create_portfolio_task_args.get("portfolio_group_name"),
                        create_portfolio_task_args.get("display_name"),
                        product.get("Name"),
                    ]
                ),
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
            for version in product.get("Versions", []):
                ensure_product_version_details_correct_task = luigi_tasks_and_targets.EnsureProductVersionDetailsCorrect(
                    region=region,
                    version=version,
                    product_args=create_product_task_args,
                )
                pipeline_versions.append(
                    {
                        "create_product_task_args": create_product_task_args,
                        "product": product,
                        "version": version,
                    }
                )
                all_tasks[
                    f"version_{p_name}_{portfolio.get('Name')}_{product.get('Name')}_{version.get('Name')}-{region}"
                ] = ensure_product_version_details_correct_task


def show_pipelines(p, format):
    pipeline_names = [f"{constants.BOOTSTRAP_STACK_NAME}-pipeline"]
    for portfolio_file_name in os.listdir(p):
        if ".yaml" in portfolio_file_name:
            p_name = portfolio_file_name.split(".")[0]
            portfolios_file_path = os.path.sep.join([p, portfolio_file_name])
            portfolios = generate_portfolios(portfolios_file_path)

            for portfolio in portfolios.get("Portfolios", []):
                nested_products = portfolio.get("Products", []) + portfolio.get(
                    "Components", []
                )
                for product in nested_products:
                    for version in product.get("Versions", []):
                        pipeline_names.append(
                            f"{p_name}-{portfolio.get('DisplayName')}-{product.get('Name')}-{version.get('Name')}-pipeline"
                        )
            for product in portfolios.get("Products", []):
                for version in product.get("Versions", []):
                    pipeline_names.append(
                        f"{product.get('Name')}-{version.get('Name')}-pipeline"
                    )
    results = {}
    for pipeline_name in pipeline_names:
        result = aws.get_details_for_pipeline(pipeline_name)
        status = result.get("status")
        if status == "Succeeded":
            status = "{green}" + status + "{/green}"
        elif status == "Failed":
            status = "{red}" + status + "{/red}"
        else:
            status = "{yellow}" + status + "{/yellow}"
        if len(result.get("sourceRevisions")) > 0:
            revision = result.get("sourceRevisions")[0]
        else:
            revision = {
                "revisionId": "N/A",
                "revisionSummary": "N/A",
            }
        results[pipeline_name] = {
            "name": pipeline_name,
            "status": result.get("status"),
            "revision_id": revision.get("revisionId"),
            "revision_summary": revision.get("revisionSummary").strip(),
        }

    if format == "table":
        table_data = [
            ["Pipeline", "Status", "Last Commit Hash", "Last Commit Message"],
        ]
        for result in results.values():
            if result.get("status") == "Succeeded":
                status = f"{{green}}{result.get('status')}{{/green}}"
            elif result.get("status") == "Failed":
                status = f"{{red}}{result.get('status')}{{/red}}"
            else:
                status = f"{{yellow}}{result.get('status')}{{/yellow}}"

            table_data.append(
                [
                    result.get("name"),
                    colorclass.Color(status),
                    result.get("revision_id"),
                    result.get("revision_summary"),
                ]
            )
        table = terminaltables.AsciiTable(table_data)
        click.echo(table.table)

    elif format == "json":
        click.echo(json.dumps(results, indent=4, default=str))


def get_stacks():
    with betterboto_client.ClientContextManager("cloudformation") as cloudformation:
        stack_summaries = []
        args = {
            "StackStatusFilter": [
                "CREATE_IN_PROGRESS",
                "CREATE_FAILED",
                "CREATE_COMPLETE",
                "ROLLBACK_IN_PROGRESS",
                "ROLLBACK_FAILED",
                "ROLLBACK_COMPLETE",
                "DELETE_IN_PROGRESS",
                "DELETE_FAILED",
                "UPDATE_IN_PROGRESS",
                "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
                "UPDATE_COMPLETE",
                "UPDATE_ROLLBACK_IN_PROGRESS",
                "UPDATE_ROLLBACK_FAILED",
                "UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS",
                "UPDATE_ROLLBACK_COMPLETE",
                "REVIEW_IN_PROGRESS",
            ]
        }
        while True:
            response = cloudformation.list_stacks(**args)
            stack_summaries += response.get("StackSummaries")
            if response.get("NextToken"):
                args["NextToken"] = response.get("NextToken")
            else:
                break

        results = {}
        for stack_summary in stack_summaries:
            results[stack_summary.get("StackName")] = stack_summary.get("StackStatus")
        return results


def deploy(p):
    stacks = get_stacks()
    for portfolio_file_name in os.listdir(p):
        if ".yaml" in portfolio_file_name:
            p_name = portfolio_file_name.split(".")[0]
            output_path = os.path.sep.join([constants.OUTPUT, p_name])
            portfolios_file_path = os.path.sep.join([p, portfolio_file_name])
            portfolios = generate_portfolios(portfolios_file_path)
            for portfolio in portfolios.get("Portfolios"):
                for product in portfolio.get("Components", []):
                    for version in product.get("Versions", []):
                        friendly_uid = "-".join(
                            [
                                p_name,
                                portfolio.get("DisplayName"),
                                product.get("Name"),
                                version.get("Name"),
                            ]
                        )
                        first_run_of_stack = stacks.get(friendly_uid, False) is False
                        logger.info(
                            "Running deploy for: {}. Is first run: {}".format(
                                friendly_uid, first_run_of_stack
                            )
                        )
                        run_deploy_for_component(
                            output_path, friendly_uid,
                        )


def get_hash_for_template(template):
    hasher = hashlib.md5()
    hasher.update(str.encode(template))
    return "{}{}".format(constants.HASH_PREFIX, hasher.hexdigest())


def run_deploy_for_component(path, friendly_uid):
    staging_template_path = os.path.sep.join(
        [path, "{}.template.yaml".format(friendly_uid)]
    )
    with open(staging_template_path) as staging_template:
        staging_template_contents = staging_template.read()

    with betterboto_client.ClientContextManager("cloudformation") as cloudformation:
        cloudformation.create_or_update(
            StackName=friendly_uid, TemplateBody=staging_template_contents,
        )
        logger.info("Finished stack: {}".format(friendly_uid))


def nuke_product_version(portfolio_name, product, version):
    click.echo("Nuking service catalog traces")
    with betterboto_client.ClientContextManager("servicecatalog") as servicecatalog:
        response = servicecatalog.list_portfolios_single_page()
        portfolio_id = None
        for portfolio_detail in response.get("PortfolioDetails"):
            if portfolio_detail.get("DisplayName") == portfolio_name:
                portfolio_id = portfolio_detail.get("Id")
                break
        if portfolio_id is None:
            raise Exception("Could not find your portfolio: {}".format(portfolio_name))
        else:
            logger.info("Portfolio_id found: {}".format(portfolio_id))
            product_name = "-".join([product, version])
            logger.info("Looking for product: {}".format(product_name))
            result = aws.get_product(servicecatalog, product)
            if result is not None:
                product_id = result.get("ProductId")
                logger.info("p: {}".format(product_id))

                logger.info("Looking for version: {}".format(version))
                response = servicecatalog.list_provisioning_artifacts(
                    ProductId=product_id,
                )

                version_id = None
                for provisioning_artifact_detail in response.get(
                    "ProvisioningArtifactDetails"
                ):
                    if provisioning_artifact_detail.get("Name") == version:
                        version_id = provisioning_artifact_detail.get("Id")
                if version_id is None:
                    click.echo("Could not find version: {}".format(version))
                else:
                    logger.info("Found version: {}".format(version_id))
                    logger.info("Deleting version: {}".format(version_id))
                    servicecatalog.delete_provisioning_artifact(
                        ProductId=product_id, ProvisioningArtifactId=version_id
                    )
                    click.echo("Deleted version: {}".format(version_id))
    click.echo("Finished nuking service catalog traces")

    click.echo("Nuking pipeline traces")
    nuke_stack(portfolio_name, product, version)
    click.echo("Finished nuking pipeline traces")


def nuke_stack(portfolio_name, product, version):
    with betterboto_client.ClientContextManager("cloudformation") as cloudformation:
        stack_name = "-".join([portfolio_name, product, version])
        click.echo("Nuking stack: {}".format(stack_name))
        try:
            cloudformation.describe_stacks(StackName=stack_name)
            cloudformation.delete_stack(StackName=stack_name)
            waiter = cloudformation.get_waiter("stack_delete_complete")
            waiter.wait(StackName=stack_name)
        except cloudformation.exceptions.ClientError as e:
            if "Stack with id {} does not exist".format(stack_name) in str(e):
                click.echo("Could not see stack")
            else:
                raise e


def bootstrap_branch(branch_name):
    constants.VERSION = "https://github.com/awslabs/aws-service-catalog-factory/archive/{}.zip".format(
        branch_name
    )
    bootstrap()


def bootstrap():
    click.echo("Starting bootstrap")
    click.echo("Starting regional deployments")
    all_regions = get_regions()
    with betterboto_client.MultiRegionClientContextManager(
        "cloudformation", all_regions
    ) as clients:
        logger.info("Creating {}-regional".format(constants.BOOTSTRAP_STACK_NAME))
        threads = []
        template = read_from_site_packages(
            "{}.template.yaml".format(
                "{}-regional".format(constants.BOOTSTRAP_STACK_NAME)
            )
        )
        template = Template(template).render(
            VERSION=constants.VERSION, ALL_REGIONS=all_regions
        )
        args = {
            "StackName": "{}-regional".format(constants.BOOTSTRAP_STACK_NAME),
            "TemplateBody": template,
            "Capabilities": ["CAPABILITY_IAM"],
            "Parameters": [
                {
                    "ParameterKey": "Version",
                    "ParameterValue": constants.VERSION,
                    "UsePreviousValue": False,
                },
            ],
        }
        for client_region, client in clients.items():
            process = Thread(
                name=client_region, target=client.create_or_update, kwargs=args
            )
            process.start()
            threads.append(process)
        for process in threads:
            process.join()
        logger.info(
            "Finished creating {}-regional".format(constants.BOOTSTRAP_STACK_NAME)
        )
    click.echo("Completed regional deployments")

    click.echo("Starting main deployment")
    s3_bucket_name = None
    with betterboto_client.ClientContextManager("cloudformation") as cloudformation:
        logger.info("Creating {}".format(constants.BOOTSTRAP_STACK_NAME))
        template = read_from_site_packages(
            "{}.template.yaml".format(constants.BOOTSTRAP_STACK_NAME)
        )
        template = Template(template).render(
            VERSION=constants.VERSION, ALL_REGIONS=all_regions
        )
        args = {
            "StackName": constants.BOOTSTRAP_STACK_NAME,
            "TemplateBody": template,
            "Capabilities": ["CAPABILITY_NAMED_IAM"],
            "Parameters": [
                {
                    "ParameterKey": "Version",
                    "ParameterValue": constants.VERSION,
                    "UsePreviousValue": False,
                },
            ],
        }
        cloudformation.create_or_update(**args)
        response = cloudformation.describe_stacks(
            StackName=constants.BOOTSTRAP_STACK_NAME
        )
        assert len(response.get("Stacks")) == 1, "Error code 1"
        stack_outputs = response.get("Stacks")[0]["Outputs"]
        for stack_output in stack_outputs:
            if stack_output.get("OutputKey") == "CatalogBucketName":
                s3_bucket_name = stack_output.get("OutputValue")
                break
        logger.info(
            "Finished creating {}. CatalogBucketName is: {}".format(
                constants.BOOTSTRAP_STACK_NAME, s3_bucket_name
            )
        )

    logger.info("Adding empty product template to s3")
    template = open(resolve_from_site_packages("empty.template.yaml")).read()
    s3 = boto3.resource("s3")
    obj = s3.Object(s3_bucket_name, "empty.template.yaml")
    obj.put(Body=template)
    logger.info("Finished adding empty product template to s3")
    logger.info("Finished bootstrap")

    with betterboto_client.ClientContextManager("codecommit") as codecommit:
        response = codecommit.get_repository(
            repositoryName=constants.SERVICE_CATALOG_FACTORY_REPO_NAME
        )
        clone_url = response.get("repositoryMetadata").get("cloneUrlHttp")
        clone_command = (
            "git clone --config 'credential.helper=!aws codecommit "
            "credential-helper $@' --config 'credential.UseHttpPath=true' "
            "{}".format(clone_url)
        )
        click.echo(
            "You need to clone your newly created repo and then seed it: \n{}".format(
                clone_command
            )
        )


def seed(complexity, p):
    target = os.path.sep.join([p, "portfolios"])
    if not os.path.exists(target):
        os.makedirs(target)

    example = "example-{}.yaml".format(complexity)
    shutil.copy2(
        resolve_from_site_packages(os.path.sep.join(["portfolios", example])),
        os.path.sep.join([target, example]),
    )


def version():
    click.echo("cli version: {}".format(constants.VERSION))
    with betterboto_client.ClientContextManager(
        "ssm", region_name=constants.HOME_REGION
    ) as ssm:
        response = ssm.get_parameter(Name="service-catalog-factory-regional-version")
        click.echo(
            "regional stack version: {} for region: {}".format(
                response.get("Parameter").get("Value"),
                response.get("Parameter").get("ARN").split(":")[3],
            )
        )
        response = config.get_stack_version()
        click.echo("stack version: {}".format(response.get("Parameter").get("Value"),))


def upload_config(config):
    with betterboto_client.ClientContextManager("ssm") as ssm:
        ssm.put_parameter(
            Name=constants.CONFIG_PARAM_NAME,
            Type="String",
            Value=yaml.safe_dump(config),
            Overwrite=True,
        )
    click.echo("Uploaded config")


def fix_issues(p):
    fix_issues_for_portfolio(p)


def fix_issues_for_portfolio(p):
    click.echo("Fixing issues for portfolios")
    for portfolio_file_name in os.listdir(p):
        if ".yaml" in portfolio_file_name:
            p_name = portfolio_file_name.split(".")[0]
            portfolios = generate_portfolios(os.path.sep.join([p, portfolio_file_name]))
            for portfolio in portfolios.get("Portfolios", []):
                for component in portfolio.get("Components", []):
                    for version in component.get("Versions", []):
                        stack_name = "-".join(
                            [
                                p_name,
                                portfolio.get("DisplayName"),
                                component.get("Name"),
                                version.get("Name"),
                            ]
                        )
                        logger.info("looking at stack: {}".format(stack_name))
                        with betterboto_client.ClientContextManager(
                            "cloudformation"
                        ) as cloudformation:
                            response = {"Stacks": []}
                            try:
                                response = cloudformation.describe_stacks(
                                    StackName=stack_name
                                )
                            except cloudformation.exceptions.ClientError as e:
                                if "Stack with id {} does not exist".format(
                                    stack_name
                                ) in str(e):
                                    click.echo(
                                        "There is no pipeline for: {}".format(
                                            stack_name
                                        )
                                    )
                                else:
                                    raise e

                            for stack in response.get("Stacks"):
                                if stack.get("StackStatus") == "ROLLBACK_COMPLETE":
                                    if click.confirm(
                                        'Found a stack: {} in status: "ROLLBACK_COMPLETE".  '
                                        "Should it be deleted?".format(stack_name)
                                    ):
                                        cloudformation.delete_stack(
                                            StackName=stack_name
                                        )
                                        waiter = cloudformation.get_waiter(
                                            "stack_delete_complete"
                                        )
                                        waiter.wait(StackName=stack_name)

    click.echo("Finished fixing issues for portfolios")


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
                kwargs={"stack_name": stack_name, "region": region,},
            )
            process.start()
            threads.append(process)
        for process in threads:
            process.join()


def delete_stack_from_a_regions(stack_name, region):
    click.echo("Deleting stack: {} from region: {}".format(stack_name, region))
    with betterboto_client.ClientContextManager(
        "cloudformation", region_name=region
    ) as cloudformation:
        cloudformation.delete_stack(StackName=stack_name)
        waiter = cloudformation.get_waiter("stack_delete_complete")
        waiter.wait(StackName=stack_name)
    click.echo("Finished")


def list_resources():
    click.echo("# Framework resources")

    click.echo("## SSM Parameters used")
    click.echo(f"- {constants.CONFIG_PARAM_NAME}")

    for file in Path(__file__).parent.resolve().glob("*.template.yaml"):
        if "empty.template.yaml" == file.name:
            continue
        template_contents = Template(open(file, "r").read()).render()
        template = cfn_tools.load_yaml(template_contents)
        click.echo(f"## Resources for stack: {file.name.split('.')[0]}")
        table_data = [
            ["Logical Name", "Resource Type", "Name",],
        ]
        table = terminaltables.AsciiTable(table_data)
        for logical_name, resource in template.get("Resources").items():
            resource_type = resource.get("Type")

            name = "-"

            type_to_name = {
                "AWS::IAM::Role": "RoleName",
                "AWS::SSM::Parameter": "Name",
                "AWS::S3::Bucket": "BucketName",
                "AWS::CodePipeline::Pipeline": "Name",
                "AWS::CodeBuild::Project": "Name",
                "AWS::CodeCommit::Repository": "RepositoryName",
            }

            if type_to_name.get(resource_type) is not None:
                name = resource.get("Properties", {}).get(
                    type_to_name.get(resource_type), "Not Specified"
                )
                if not isinstance(name, str):
                    name = cfn_tools.dump_yaml(name)

            table_data.append([logical_name, resource_type, name])

        click.echo(table.table)
    click.echo(f"n.b. AWS::StackName evaluates to {constants.BOOTSTRAP_STACK_NAME}")


def import_product_set(f, name, portfolio_name):
    url = f"https://raw.githubusercontent.com/awslabs/aws-service-catalog-products/master/{name}/portfolio.yaml"
    response = requests.get(url)
    logger.info(f"Getting {url}")
    source_portfolio = yaml.safe_load(f.read())
    target = None
    if portfolio_name is None:
        if source_portfolio.get("Products") is None:
            source_portfolio.get["Products"] = {}
        target = source_portfolio.get["Products"]
    else:
        if source_portfolio.get("Portfolios") is None:
            source_portfolio["Portfolios"] = []
        for p in source_portfolio.get("Portfolios"):
            if p.get("DisplayName") == portfolio_name:
                if p.get("Products"):
                    target = p.get("Products")
                elif p.get("Components"):
                    target = p.get("Components")
                else:
                    target = p["Products"] = []
        if target is None:
            p = {
                "DisplayName": portfolio_name,
                "Products": [],
            }
            target = p.get("Products")
            source_portfolio["Portfolios"].append(p)

    portfolio_segment = yaml.safe_load(response.text)
    products = portfolio_segment.get("Portfolios").get(
        "Components", []
    ) + portfolio_segment.get("Portfolios").get("Products", [])
    for product in products:
        target.append(product)
        for version in product.get("Versions"):
            if version.get("Source").get("Provider") == "CodeCommit":
                configuration = version.get("Source").get("Configuration")
                branch_name = configuration.get("BranchName")
                repository_name = configuration.get("RepositoryName")

                os.system(
                    f"aws codecommit create-repository --repository-name {repository_name}"
                )
                command = (
                    "git clone "
                    "--config 'credential.helper=!aws codecommit credential-helper $@' "
                    "--config 'credential.UseHttpPath=true' "
                    f"https://git-codecommit.{constants.HOME_REGION}.amazonaws.com/v1/repos/{repository_name}"
                )
                os.system(command)
                remote_name = repository_name.replace(f"{name}-", "")
                source = f"https://github.com/awslabs/aws-service-catalog-products/trunk/{name}/{remote_name}/{version.get('Name')}"
                os.system(f"svn export {source} {repository_name} --force")
                if branch_name == "master":
                    os.system(
                        f"cd {repository_name} && git add . && git commit -am 'initial add' && git push"
                    )
                else:
                    os.system(
                        f"cd {repository_name} && git checkout -b {branch_name} && git add . && git commit -am 'initial add' && git push"
                    )

    with open(f.name, "w") as f:
        f.write(yaml.safe_dump(source_portfolio))


def get_portfolios_by_file_name(portfolio_file_name):
    with betterboto_client.ClientContextManager("codecommit") as codecommit:
        content = codecommit.get_file(
            repositoryName=constants.SERVICE_CATALOG_FACTORY_REPO_NAME,
            filePath=f"portfolios/{portfolio_file_name}",
        ).get("fileContent")
        return yaml.safe_load(content)


def put_portfolios_by_file_name(portfolio_file_name, portfolios):
    logger.info(f"Saving portfolio file: {portfolio_file_name}")
    with betterboto_client.ClientContextManager("codecommit") as codecommit:
        parent_commit_id = (
            codecommit.get_branch(
                repositoryName=constants.SERVICE_CATALOG_FACTORY_REPO_NAME,
                branchName="master",
            )
            .get("branch")
            .get("commitId")
        )
        codecommit.put_file(
            repositoryName=constants.SERVICE_CATALOG_FACTORY_REPO_NAME,
            branchName="master",
            fileContent=yaml.safe_dump(portfolios),
            parentCommitId=parent_commit_id,
            commitMessage="Auto generated commit",
            filePath=f"portfolios/{portfolio_file_name}",
        )


def portfolio_has_product(portfolio, product_name):
    logger.info(f"Looking for product: {product_name}")
    products = portfolio.get("Components", []) + portfolio.get("Products", [])
    for p in products:
        if p.get("Name") == product_name:
            return True
    return False


def ensure_code_commit_repo(details):
    logger.info(f"ensuring code commit rep")
    if details.get("Source", {}).get("Provider", "").lower() == "codecommit":
        logger.info(f"Codecommit repo defined, carrying on")
        configuration = details.get("Source").get("Configuration")
        branch_name = configuration.get("BranchName")
        repository_name = configuration.get("RepositoryName")
        with betterboto_client.ClientContextManager("codecommit") as codecommit:
            repo_empty = False
            all_branches = []
            try:
                all_branches = codecommit.list_branches_single_page(
                    repositoryName=repository_name
                ).get("branches")
                logger.info(f"Codecommit repo exists, carrying on")
            except codecommit.exceptions.RepositoryDoesNotExistException:
                logger.info(f"Codecommit does not exist, creating it")
                repo_empty = True
                codecommit.create_repository(repositoryName=repository_name)

            if branch_name not in all_branches:
                logger.info(f"Codecommit branch not found, creating it")
                if repo_empty:
                    logger.info(
                        f"Repo was empty, creating first commit on the branch: {branch_name}"
                    )
                    parent_commit_id = codecommit.create_commit(
                        repositoryName=repository_name,
                        branchName=branch_name,
                        commitMessage="Auto generated commit",
                        putFiles=[
                            {
                                "filePath": "product.template.yaml",
                                "fileMode": "NORMAL",
                                "fileContent": "",
                            }
                        ],
                    ).get("commitId")
                else:
                    if "master" not in all_branches:
                        raise Exception(
                            f"{repository_name} has no 'master' branch to branch"
                        )
                    logger.info(
                        f"Repo was not empty, go to create the branch: {branch_name} from master"
                    )
                    parent_commit_id = (
                        codecommit.get_branch(
                            repositoryName=repository_name, branchName="master",
                        )
                        .get("branch")
                        .get("commitId")
                    )

                logger.info(f"Creating the branch: {branch_name}")
                codecommit.create_branch(
                    repositoryName=repository_name,
                    branchName=branch_name,
                    commitId=parent_commit_id,
                )


def add_product_to_portfolio(portfolio_file_name, portfolio_display_name, product):
    logger.info(
        f"adding product: {product.get('Name')} to portfolio: {portfolio_display_name} in: {portfolio_file_name}"
    )
    portfolios = get_portfolios_by_file_name(portfolio_file_name)
    for portfolio in portfolios.get("Portfolios"):
        if portfolio.get("DisplayName") == portfolio_display_name:
            if not portfolio_has_product(portfolio, product.get("Name")):
                if portfolio.get("Products", None) is None:
                    portfolio["Products"] = []
                portfolio["Products"].append(product)
                ensure_code_commit_repo(product)
                return put_portfolios_by_file_name(portfolio_file_name, portfolios)
            else:
                raise Exception(
                    f"Portfolio: {portfolio_file_name} {portfolio_display_name} contains product: {product.get('Name')}"
                )
    raise Exception(f"Could not find portfolio {portfolio_display_name}")


def remove_product_from_portfolio(
    portfolio_file_name, portfolio_display_name, product_name
):
    logger.info(
        f"removing product: {product_name} to portfolio: {portfolio_display_name} in: {portfolio_file_name}"
    )
    portfolios = get_portfolios_by_file_name(portfolio_file_name)
    removed = False
    for portfolio in portfolios.get("Portfolios"):
        if portfolio.get("DisplayName") == portfolio_display_name:
            if portfolio_has_product(portfolio, product_name):
                p, where = get_product_from_portfolio(portfolio, product_name)
                portfolio.get(where).remove(p)
                put_portfolios_by_file_name(portfolio_file_name, portfolios)
                removed = True

    if not removed:
        for product in portfolios.get("Products"):
            if product.get("Name") == product_name:
                if portfolio_display_name in product.get("Portfolios", []):
                    product.get("Portfolios").remove(portfolio_display_name)
                    put_portfolios_by_file_name(portfolio_file_name, portfolios)
                    removed = True

    if not removed:
        raise Exception(f"Could not remove product from portfolio")


def get_product_from_portfolio(portfolio, product_name):
    for p in portfolio.get("Components", []):
        if product_name == p.get("Name"):
            return p, "Components"
    for p in portfolio.get("Products", []):
        if product_name == p.get("Name"):
            return p, "Products"


def add_version_to_product(
    portfolio_file_name, portfolio_display_name, product_name, version
):
    logger.info(
        f"adding version: {version.get('Name')} to product: {product_name} portfolio: {portfolio_display_name} in: {portfolio_file_name}"
    )
    portfolios = get_portfolios_by_file_name(portfolio_file_name)
    for portfolio in portfolios.get("Portfolios"):
        if portfolio.get("DisplayName") == portfolio_display_name:
            if portfolio_has_product(portfolio, product_name):
                p, where = get_product_from_portfolio(portfolio, product_name)
                for v in p.get("Versions", []):
                    if v.get("Name") == version.get("Name"):
                        raise Exception(
                            f"Portfolio: {portfolio_file_name} {portfolio_display_name} contains version: {version.get('Name')}"
                        )
                if p.get("Versions", None) is None:
                    p["Versions"] = []
                p["Versions"].append(version)
                ensure_code_commit_repo(version)
                return put_portfolios_by_file_name(portfolio_file_name, portfolios)
            else:
                raise Exception(
                    f"Portfolio: {portfolio_file_name} {portfolio_display_name} does not contain product: {product_name}"
                )
    raise Exception(f"Could not find portfolio {portfolio_display_name}")


def remove_version_from_product(
    portfolio_file_name, portfolio_display_name, product_name, version_name
):
    logger.info(
        f"removing version: {version_name} from product: {product_name} portfolio: {portfolio_display_name} in: {portfolio_file_name}"
    )
    portfolios = get_portfolios_by_file_name(portfolio_file_name)
    for portfolio in portfolios.get("Portfolios"):
        if portfolio.get("DisplayName") == portfolio_display_name:
            if portfolio_has_product(portfolio, product_name):
                p, where = get_product_from_portfolio(portfolio, product_name)
                for v in p.get("Versions", []):
                    if v.get("Name") == version_name:
                        p["Versions"].remove(v)
                        return put_portfolios_by_file_name(
                            portfolio_file_name, portfolios
                        )
                raise Exception(
                    f"Portfolio: {portfolio_file_name} {portfolio_display_name} does not contain version: {version_name}"
                )
            else:
                raise Exception(
                    f"Portfolio: {portfolio_file_name} {portfolio_display_name} does not contain product: {product_name}"
                )
    raise Exception(f"Could not find portfolio {portfolio_display_name}")


def generate_terraform_template(uid, terraform_version, tf_vars):
    template = utils.ENV.get_template(constants.TERRAFORM_TEMPLATE)
    return template.render(
        FACTORY_VERSION=constants.VERSION,
        PROVISIONER_VERSION=terraform_version,
        TF_VARS=tf_vars,
        PUPPET_ACCOUNT_ID=os.environ.get("ACCOUNT_ID"),
        UID=uid,
    )


def add_secret(secret_name, oauth_token, secret_token):
    with betterboto_client.ClientContextManager("secretsmanager") as secretsmanager:
        try:
            secretsmanager.create_secret(
                Name=secret_name,
                SecretString=json.dumps(
                    {
                        "OAuthToken": oauth_token,
                        "SecretToken": secret_token or oauth_token,
                    }
                ),
            )
        except secretsmanager.exceptions.ResourceExistsException:
            secretsmanager.put_secret_value(
                SecretId=secret_name,
                SecretString=json.dumps(
                    {
                        "OAuthToken": oauth_token,
                        "SecretToken": secret_token or oauth_token,
                    }
                ),
                VersionStages=["AWSCURRENT",],
            )
    click.echo("Uploaded secret")


def set_regions(regions):
    with betterboto_client.ClientContextManager(
        "ssm", region_name=constants.HOME_REGION
    ) as ssm:
        try:
            response = ssm.get_parameter(Name=constants.CONFIG_PARAM_NAME)
            config = yaml.safe_load(response.get("Parameter").get("Value"))
        except ssm.exceptions.ParameterNotFound:
            config = {}
        config["regions"] = regions if len(regions) > 1 else regions[0].split(",")
        upload_config(config)


def generate_launch_constraints(p):
    logger.info("generating launch contraints")
    account_id = os.getenv("CODEBUILD_BUILD_ARN").split(":")[4]
    all_regions = get_regions()
    products_by_portfolio = {}
    logger.info("Building up portfolios list")
    for portfolio_file_name in os.listdir(p):
        if ".yaml" in portfolio_file_name:
            p_name = portfolio_file_name.split(".")[0]
            portfolios_file_path = os.path.sep.join([p, portfolio_file_name])
            portfolios = generate_portfolios(portfolios_file_path)
            for portfolio in portfolios.get("Portfolios", []):
                portfolio_name = f"{p_name}-{portfolio.get('DisplayName')}"
                products_by_portfolio[portfolio_name] = []
                products = portfolio.get("Products", []) + portfolio.get(
                    "Components", []
                )
                for product in products:
                    if (
                        product.get("Constraints", {})
                        .get("Launch", {})
                        .get("LocalRoleName")
                        is not None
                    ):
                        products_by_portfolio[portfolio_name].append(
                            {
                                "product_name": product.get("Name"),
                                "local_role_name": product.get("Constraints", {})
                                .get("Launch", {})
                                .get("LocalRoleName"),
                            }
                        )

            products = portfolios.get("Products", []) + portfolios.get("Components", [])
            for product in products:
                if (
                    product.get("Constraints", {})
                    .get("Launch", {})
                    .get("LocalRoleName")
                    is not None
                ):
                    for portfolio_name in product.get("Portfolios"):
                        products_by_portfolio[f"{p_name}-{portfolio_name}"].append(
                            {
                                "product_name": product.get("Name"),
                                "local_role_name": product.get("Constraints", {})
                                .get("Launch", {})
                                .get("LocalRoleName"),
                            }
                        )

    logger.info(f"Finished building up portfolio list: {products_by_portfolio}")

    nested_template = read_from_site_packages(
        "templates/constraint-launch-role-nested.template.yaml"
    )
    parent_template = read_from_site_packages(
        "templates/constraint-launch-role-parent.template.yaml"
    )

    logger.info("starting to write the template")
    if not os.path.exists(f"output/constraints/launch-role"):
        os.makedirs(f"output/constraints/launch-role")

    for region in all_regions:
        logger.info(f"looking at region {region}")
        parent_template_context = []
        for portfolios_name, launch_role_constraints in products_by_portfolio.items():
            nested_template_context = []
            with open(
                os.path.sep.join(
                    [
                        "output",
                        "CreatePortfolioTask",
                        f"{region}-{portfolios_name}.json",
                    ]
                ),
                "r",
            ) as portfolio_json_file:
                portfolio_json = json.loads(portfolio_json_file.read())
                portfolio_id = portfolio_json.get("Id")
            for launch_role_constraint in launch_role_constraints:
                with open(
                    os.path.sep.join(
                        [
                            "output",
                            "CreateProductTask",
                            f'{region}-{launch_role_constraint.get("product_name")}.json',
                        ]
                    ),
                    "r",
                ) as product_json_file:
                    product_json = json.loads(product_json_file.read())
                    product_id = product_json.get("ProductId")
                nested_template_context.append(
                    {
                        "uid": f"{portfolio_id}{product_id}".replace("-", ""),
                        "product_id": product_id,
                        "portfolio_id": portfolio_id,
                        "local_role_name": launch_role_constraint.get(
                            "local_role_name"
                        ),
                    }
                )

            if len(nested_template_context) > 0:
                nested_template_name = f"{region}-{portfolio_id}.template.yaml"
                logger.info(
                    f"About to write a template: output/constraints/launch-role/{nested_template_name}"
                )
                hash_suffix = datetime.now().strftime("%Y-%d-%m--%H:%M:%S-%f")
                nested_content_file = f"output/constraints/launch-role/{nested_template_name}-{hash_suffix}.template.yaml"
                bucket_name = f"sc-factory-pipeline-artifacts-{account_id}-{region}"
                object_key = f"templates/constraints/launch-role/{nested_template_name}-{hash_suffix}.template.yaml"

                nested_content = Template(nested_template).render(
                    VERSION=constants.VERSION,
                    ALL_REGIONS=all_regions,
                    constraints=nested_template_context,
                )
                with open(nested_content_file, "w") as cfn:
                    cfn.write(nested_content)
                logger.info(f"Wrote nested template to {nested_content_file}")
                s3 = boto3.resource("s3")
                s3.meta.client.upload_file(
                    nested_content_file, bucket_name, object_key,
                )
                logger.info(
                    f"Uploaded nested template to s3://{bucket_name}:{object_key}"
                )
                nested_template_url = (
                    f"https://{bucket_name}.s3.{region}.amazonaws.com/{object_key}"
                )
                parent_template_context.append(
                    {
                        "uid": f"{region}{portfolio_id}".replace("-", ""),
                        "url": nested_template_url,
                    }
                )

        logger.info(
            f"About to write a template: output/constraints/launch-role/{region}.template.yaml"
        )
        with open(f"output/constraints/launch-role/{region}.template.yaml", "w") as cfn:
            main_template = Template(parent_template).render(
                VERSION=constants.VERSION,
                ALL_REGIONS=all_regions,
                nested_templates=parent_template_context,
            )
            logger.info(main_template)
            cfn.write(main_template)
    logger.info("finished writing the template")


def get_source_for_pipeline(pipeline_name, execution_id):
    with betterboto_client.ClientContextManager("codepipeline",) as codepipeline:
        paginator = codepipeline.get_paginator("list_pipeline_executions")
        pages = paginator.paginate(
            pipelineName=pipeline_name, PaginationConfig={"PageSize": 100,}
        )
        for page in pages:
            for pipeline_execution_summary in page.get(
                "pipelineExecutionSummaries", []
            ):
                if execution_id == pipeline_execution_summary.get(
                    "pipelineExecutionId"
                ):
                    trigger = pipeline_execution_summary.get("trigger")
                    if trigger.get("triggerType") == "CloudWatchEvent":
                        triggerDetail = trigger.get("triggerDetail")
                        with betterboto_client.ClientContextManager(
                            "events",
                        ) as events:
                            rule = events.describe_rule(
                                Name=triggerDetail.split("/")[-1]
                            )
                            source = rule.get("Description")
                            return source


def print_source_directory(pipeline_name, execution_id, artifact):
    source = get_source_for_pipeline(pipeline_name, execution_id)
    click.echo(os.getenv(f"CODEBUILD_SRC_DIR_{artifact}{source}", "."))
    return


def update_provisioned_product(region, name, product_id, description, template_url):
    with betterboto_client.ClientContextManager(
        "servicecatalog", region_name=region
    ) as servicecatalog:
        response = servicecatalog.create_provisioning_artifact(
            ProductId=product_id,
            Parameters={
                "Name": name,
                "Description": description,
                "Info": {"LoadTemplateFromURL": template_url},
                "Type": "CLOUD_FORMATION_TEMPLATE",
                "DisableTemplateValidation": False,
            },
        )
        new_provisioning_artifact_id = response.get("ProvisioningArtifactDetail").get(
            "Id"
        )
        status = "CREATING"
        while status == "CREATING":
            time.sleep(3)
            status = servicecatalog.describe_provisioning_artifact(
                ProductId=product_id,
                ProvisioningArtifactId=new_provisioning_artifact_id,
            ).get("Status")

        if status == "FAILED":
            raise Exception("Creating the provisioning artifact failed")

        response = servicecatalog.list_provisioning_artifacts_single_page(
            ProductId=product_id
        )
        provisioning_artifact_details = response.get("ProvisioningArtifactDetails", [])
        for provisioning_artifact_detail in provisioning_artifact_details:
            if (
                provisioning_artifact_detail.get("Name") == name
                and provisioning_artifact_detail.get("Id")
                != new_provisioning_artifact_id
            ):
                servicecatalog.delete_provisioning_artifact(
                    ProductId=product_id,
                    ProvisioningArtifactId=provisioning_artifact_detail.get("Id"),
                )
