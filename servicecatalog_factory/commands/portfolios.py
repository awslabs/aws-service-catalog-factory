#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import json
import os
import time
from datetime import datetime

import boto3
import click
import requests
import yaml
from betterboto import client as betterboto_client
from deepmerge import always_merger
from jinja2 import Template

from servicecatalog_factory.workflow.codecommit import create_code_repo_task
from servicecatalog_factory.workflow.portfolios import (
    associate_product_with_portfolio_task,
)
from servicecatalog_factory.workflow.portfolios import (
    create_combined_product_pipeline_task,
)
from servicecatalog_factory.workflow.portfolios import create_portfolio_association_task
from servicecatalog_factory.workflow.portfolios import create_portfolio_task
from servicecatalog_factory.workflow.portfolios import create_product_task
from servicecatalog_factory.workflow.portfolios import create_version_pipeline_task
from servicecatalog_factory.workflow.portfolios import (
    create_version_pipeline_template_task,
)
from servicecatalog_factory.workflow.portfolios import delete_a_version_task
from servicecatalog_factory.workflow.portfolios import delete_product_task
from servicecatalog_factory.workflow.portfolios import (
    ensure_product_version_details_correct_task,
)
from servicecatalog_factory import aws
from servicecatalog_factory import config
from servicecatalog_factory import constants
from servicecatalog_factory import utils
from servicecatalog_factory.utilities.assets import read_from_site_packages

import logging

from servicecatalog_factory.template_builder.cdk import (
    product_template as cdk_product_template,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_regions():
    return config.get_regions()


def generate_portfolios(portfolios_file_path):
    logger.info("Loading portfolio: {}".format(portfolios_file_path))
    with open(portfolios_file_path) as portfolios_file:
        portfolio_file_base_path = os.path.dirname(portfolios_file_path)
        portfolio_file_name = portfolios_file_path.split("/")[-1]
        portfolio_file_name = portfolio_file_name.replace(".yaml", "")
        portfolios_file_contents = portfolios_file.read()
        portfolios = yaml.safe_load(portfolios_file_contents)
        logger.info("Checking for external config")
        for portfolio in portfolios.get("Portfolios", []):
            check_for_external_definitions_for(
                portfolio, portfolio_file_name, "Components", portfolio_file_base_path
            )
            check_for_external_definitions_for(
                portfolio, portfolio_file_name, "Products", portfolio_file_base_path
            )
        return portfolios


def check_for_external_definitions_for(
    portfolio, portfolio_file_name, type, portfolio_file_base_path
):
    # Looks and checks for products in ignored/src/ServiceCatalogFactory/portfolios/portfolio<without.yaml>/Portfolios/<portfolio-display-name>/Products
    portfolio_products_path = os.path.sep.join(
        [
            portfolio_file_base_path,
            portfolio_file_name,
            "Portfolios",
            portfolio.get("DisplayName"),
            type,
        ]
    )

    # Allows for creation of Products in portfolio or append based on file in the products folder
    if os.path.exists(portfolio_products_path) and type == "Products":
        if portfolio.get("Products") is None:
            portfolio["Products"] = []

        # Find all products
        external_products = os.listdir(portfolio_products_path)

        # Loop over product folders
        for external_product in external_products:

            external_product_spec_file_path = os.path.sep.join(
                [portfolio_products_path, external_product, f"{external_product}.yaml",]
            )

            # Only append products defined in spec files as products could have been defined in the portfolio
            if os.path.exists(external_product_spec_file_path):
                external_product_spec_file = open(
                    external_product_spec_file_path, "r",
                ).read()
                external_product_yaml = yaml.safe_load(external_product_spec_file)
                external_product_yaml["Name"] = external_product
                portfolio["Products"].append(external_product_yaml)

    # Versions
    for component in portfolio.get(type, []):
        portfolio_external_components_specification_path = os.path.sep.join(
            [
                portfolio_file_base_path,
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


def generate_for_portfolios_versions(
    all_regions, all_tasks, factory_version, pipeline_versions, products_by_region,
):
    for version_pipeline_to_build in pipeline_versions:
        version_details = version_pipeline_to_build.get("version")
        product_details = version_pipeline_to_build.get("product")

        if version_details.get("Status", "active") == "terminated":
            product_name = product_details.get("Name")

            for region, product_args in products_by_region.get(product_name).items():
                task_id = f"pipeline_template_{product_name}-{version_details.get('Name')}-{region}"
                all_tasks[task_id] = delete_a_version_task.DeleteAVersionTask(
                    product_args=product_args, version=version_details.get("Name"),
                )

        else:
            product_name = product_details.get("Name")
            tags = {}
            for tag in product_details.get("Tags", []):
                tags[tag.get("Key")] = tag.get("Value")

            for tag in version_details.get("Tags", []):
                tags[tag.get("Key")] = tag.get("Value")
            tag_list = []
            for tag_name, value in tags.items():
                tag_list.append({"Key": tag_name, "Value": value})

            create_args = {
                "all_regions": all_regions,
                "version": version_details,
                "product": product_details,
                "provisioner": version_details.get(
                    "Provisioner", {"Type": "CloudFormation"}
                ),
                "template": utils.merge(
                    product_details.get("Template", {}),
                    version_details.get("Template", {}),
                ),
                "products_args_by_region": products_by_region.get(product_name),
                "factory_version": factory_version,
                "tags": tag_list,
            }
            if version_details.get("Source", {}).get("Configuration", {}).get("Code"):
                source = always_merger.merge(
                    product_details.get("Source", {}), version_details.get("Source", {})
                )
                configuration = source.get("Configuration")
                code = configuration.get("Code")
                all_tasks[
                    f"create_code_repo_task-{configuration.get('RepositoryName')}-{configuration.get('BranchName')}"
                ] = create_code_repo_task.CreateCodeRepoTask(
                    repository_name=configuration.get("RepositoryName"),
                    branch_name=configuration.get("BranchName"),
                    bucket=code.get("S3").get("Bucket"),
                    key=code.get("S3").get("Key"),
                )
            t = create_version_pipeline_template_task.CreateVersionPipelineTemplateTask(
                **create_args
            )
            logger.info(
                f"created pipeline_template_{product_name}-{version_details.get('Name')}"
            )
            all_tasks[
                f"pipeline_template_{product_name}-{version_details.get('Name')}"
            ] = t

            t = create_version_pipeline_task.CreateVersionPipelineTask(
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
                        all_tasks[task_id] = delete_a_version_task.DeleteAVersionTask(
                            product_args=product_args,
                            version=version.get("version").get("Name"),
                        )
                else:
                    task_id = f"pipeline_template_{product_name}_combined"
                    all_tasks[
                        task_id
                    ] = create_combined_product_pipeline_task.CreateCombinedProductPipelineTask(
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
            ] = delete_product_task.DeleteProductTask(
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

        for portfolio in product.get("Portfolios", []):
            create_portfolio_task_args = all_tasks[
                f"portfolio_{p_name}_{portfolio}-{region}"
            ].param_kwargs
            all_tasks[
                f"association_{portfolio}_{product.get('Name')}-{region}"
            ] = associate_product_with_portfolio_task.AssociateProductWithPortfolioTask(
                region=region,
                portfolio_args=create_portfolio_task_args,
                product_args=create_product_task_args,
            )

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
            all_tasks[
                f"version_{product.get('Name')}_{version.get('Name')}-{region}"
            ] = ensure_product_version_details_correct_task.EnsureProductVersionDetailsCorrect(
                region=region, version=version, product_args=create_product_task_args,
            )

        all_tasks[f"product_{p_name}-{region}"] = create_product_task.CreateProductTask(
            **create_product_task_args
        )


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
        all_tasks[
            f"portfolio_{p_name}_{portfolio.get('DisplayName')}-{region}"
        ] = create_portfolio_task.CreatePortfolioTask(**create_portfolio_task_args)
        all_tasks[
            f"portfolio_associations_{p_name}_{portfolio.get('DisplayName')}-{region}"
        ] = create_portfolio_association_task.CreatePortfolioAssociationTask(
            **create_portfolio_task_args,
            associations=portfolio.get("Associations", []),
            factory_version=factory_version,
        )
        nested_products = portfolio.get("Products", []) + portfolio.get(
            "Components", []
        )
        for product in nested_products:
            product_uid = f"{product.get('Name')}"

            if product.get("Status", None) == "terminated":
                all_tasks[
                    f"delete_product_{p_name}_{portfolio.get('DisplayName')}_{product.get('Name')}-{region}"
                ] = delete_product_task.DeleteProductTask(
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

            all_tasks[
                f"product_{p_name}_{portfolio.get('DisplayName')}_{product.get('Name')}-{region}"
            ] = create_product_task.CreateProductTask(**create_product_task_args)

            all_tasks[
                f"association_{p_name}_{portfolio.get('DisplayName')}_{product.get('Name')}-{region}"
            ] = associate_product_with_portfolio_task.AssociateProductWithPortfolioTask(
                region=region,
                portfolio_args=create_portfolio_task_args,
                product_args=create_product_task_args,
            )
            for version in product.get("Versions", []):
                pipeline_versions.append(
                    {
                        "create_product_task_args": create_product_task_args,
                        "product": product,
                        "version": version,
                    }
                )
                all_tasks[
                    f"version_{p_name}_{portfolio.get('Name')}_{product.get('Name')}_{version.get('Name')}-{region}"
                ] = ensure_product_version_details_correct_task.EnsureProductVersionDetailsCorrect(
                    region=region,
                    version=version,
                    product_args=create_product_task_args,
                )


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
        if os.path.exists(f"output/constraints/launch-role/{region}.template.yaml"):
            with open(
                f"output/constraints/launch-role/{region}.template.yaml", "w"
            ) as cfn:
                main_template = Template(parent_template).render(
                    VERSION=constants.VERSION,
                    ALL_REGIONS=all_regions,
                    nested_templates=parent_template_context,
                )
                logger.info(main_template)
                cfn.write(main_template)
    logger.info("finished writing the template")


def deploy_launch_constraints(partition):
    account_id = os.getenv("CODEBUILD_BUILD_ARN").split(":")[4]
    all_regions = get_regions()

    for region in all_regions:
        if os.path.exists(f"output/constraints/launch-role/{region}.template.yaml"):
            with betterboto_client.ClientContextManager(
                "cloudformation", region_name=region
            ) as cfn:
                cfn.ensure_deleted(
                    StackName=f"servicecatalog-factory-constraints-launch-role-{region}"
                )
                template_body = open(
                    f"output/constraints/launch-role/{region}.template.yaml", "r"
                ).read()
                cfn.create_or_update(
                    StackName=f"servicecatalog-factory-constraints-launch-role-v2-{region}",
                    TemplateBody=template_body,
                    RoleARN=f"arn:{partition}:iam::{account_id}:role/servicecatalog-factory/FactoryCloudFormationDeployRole",
                )


def get_source_for_pipeline(pipeline_name, execution_id):
    with betterboto_client.ClientContextManager("codepipeline",) as codepipeline:
        paginator = codepipeline.get_paginator("list_pipeline_executions")
        pages = paginator.paginate(
            pipelineName=pipeline_name, PaginationConfig={"PageSize": 100,},
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
    with betterboto_client.ClientContextManager("cloudformation") as cloudformation:
        cloudformation.ensure_deleted(
            StackName="-".join([portfolio_name, product, version])
        )

    click.echo("Finished nuking pipeline traces")


def generate_template(
    provisioner_name, provisioner_version, product_name, product_version, p
) -> str:
    with betterboto_client.ClientContextManager("s3") as s3:
        body = (
            s3.get_object(
                Bucket=f"sc-factory-artifacts-{os.environ.get('ACCOUNT_ID')}-{os.environ.get('REGION')}",
                Key=f"{provisioner_name}/{provisioner_version}/{product_name}/{product_version}/template.json",
            )
            .get("Body")
            .read()
        )
        template = json.loads(body)
        if provisioner_name == "CDK" and provisioner_version == "1.0.0":
            return cdk_product_template.create_cdk_pipeline(
                provisioner_name,
                provisioner_version,
                product_name,
                product_version,
                template,
                p,
            ).to_yaml(clean_up=True)
        raise Exception(f"Unknown {provisioner_name} and {provisioner_version}")


def generate(portfolios_path, factory_version):
    all_tasks = {}
    all_regions = config.get_regions()
    products_by_region = {}
    pipeline_versions = list()
    products_versions = dict()

    if os.path.exists(portfolios_path):
        for portfolio_file_name in os.listdir(portfolios_path):
            if ".yaml" in portfolio_file_name:
                p_name = portfolio_file_name.split(".")[0]
                portfolios_file_path = os.path.sep.join(
                    [portfolios_path, portfolio_file_name]
                )
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
            all_regions,
            all_tasks,
            factory_version,
            pipeline_versions,
            products_by_region,
        )
        generate_for_products_versions(
            all_regions,
            all_tasks,
            factory_version,
            products_versions,
            products_by_region,
        )

    return list(all_tasks.values())
