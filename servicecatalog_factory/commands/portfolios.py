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
from servicecatalog_factory import aws
from servicecatalog_factory import config
from servicecatalog_factory import constants
from servicecatalog_factory import utils

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
            portfolio.get("DisplayName", portfolio.get("PortfolioName")),
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
                portfolio.get("DisplayName", portfolio.get("PortfolioName")),
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


def get_action_executions_for(pipeline_name, execution_id):
    with betterboto_client.ClientContextManager("codepipeline",) as codepipeline:
        result = codepipeline.list_action_executions(
            pipelineName=pipeline_name,
            filter={"pipelineExecutionId": execution_id},
            maxResults=100,
        )
        return result.get("actionExecutionDetails")


def get_pipeline_execution_for(pipeline_name, execution_id):
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
                    return pipeline_execution_summary


def print_source_directory(pipeline_name, execution_id):
    actions = get_action_executions_for(pipeline_name, execution_id)
    source_actions = list()
    for action in actions:
        if action.get("stageName") == "Source":
            source_actions.append(action)

    source_actions.sort(key=lambda x: x.get("lastUpdateTime"))
    first_source_name = source_actions[0].get("actionName")

    if len(source_actions) > 1:
        execution = get_pipeline_execution_for(pipeline_name, execution_id)
        trigger = execution.get("trigger")
        trigger_type = trigger.get("triggerType")
        trigger_detail = trigger.get("triggerDetail")

        if trigger_type in ["CreatePipeline", "StartPipelineExecution"]:
            source = first_source_name
        elif trigger_type == "PollForSourceChanges":
            source = trigger_detail
        elif trigger_type == "CloudWatchEvent":
            with betterboto_client.ClientContextManager("events",) as events:
                rule = events.describe_rule(Name=trigger_detail.split("/")[-1])
                source = rule.get("Description")
        elif trigger_type == "Webhook":
            raise Exception(f"NOT IMPLEMENTED YET: {trigger_type}: {trigger_detail}")
        elif trigger_type == "PutActionRevision":
            raise Exception(f"NOT IMPLEMENTED YET: {trigger_type}: {trigger_detail}")
        else:
            raise Exception(f"NOT IMPLEMENTED YET: {trigger_type}: {trigger_detail}")

    else:
        source = first_source_name

    codebuild_src_dir = os.getenv(
        f"CODEBUILD_SRC_DIR_{source}", os.getenv("CODEBUILD_SRC_DIR", ".")
    )
    click.echo(codebuild_src_dir)
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
