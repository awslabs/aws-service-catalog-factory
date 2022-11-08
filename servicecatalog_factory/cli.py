#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import os
from datetime import datetime

import yaml

from servicecatalog_factory import environmental_variables
from servicecatalog_factory.commands import bootstrap as bootstrap_commands
from servicecatalog_factory.commands import configuration_management
from servicecatalog_factory.commands import generate as generate_commands
from servicecatalog_factory.commands import list_resources as list_resources_commands
from servicecatalog_factory.commands import portfolios
from servicecatalog_factory.commands import seed as seed_commands
from servicecatalog_factory.commands import show_pipelines as show_pipelines_commands
from servicecatalog_factory.commands import stacks
from servicecatalog_factory.commands import task_reference as task_reference_commands
from servicecatalog_factory import constants
from servicecatalog_factory.commands import validate as validate_commands
from servicecatalog_factory.commands import version as version_commands
from servicecatalog_factory.commands import management as management_commands
from servicecatalog_factory import cloudformation_servicecatalog_deploy_action
import logging
import click

logger = logging.getLogger()
logger.setLevel(logging.INFO)


@click.group()
@click.option("--info/--no-info", default=False)
@click.option("--info-line-numbers/--no-info-line-numbers", default=False)
def cli(info, info_line_numbers):
    """cli for pipeline tools"""
    if info:
        logging.basicConfig(
            format="%(levelname)s %(threadName)s %(message)s", level=logging.INFO
        )
    if info_line_numbers:
        logging.basicConfig(
            format="%(levelname)s %(threadName)s [%(filename)s:%(lineno)d] %(message)s",
            datefmt="%Y-%m-%d:%H:%M:%S",
            level=logging.INFO,
        )


@cli.command()
@click.argument("p", type=click.Path(exists=True))
def validate(p):
    validate_commands.validate(p)


def setup_config():
    if os.environ.get(environmental_variables.CACHE_INVALIDATOR):
        click.echo(
            f"Found existing CACHE_INVALIDATOR: {os.environ.get(environmental_variables.CACHE_INVALIDATOR)}"
        )
    else:
        os.environ[environmental_variables.CACHE_INVALIDATOR] = str(datetime.now())


@cli.command()
@click.argument("p", type=click.Path(exists=True))
def generate(p):
    setup_config()
    generate_commands.generate(p)


@cli.command()
@click.argument("p", type=click.Path(exists=True))
@click.option(
    "--format", "-f", type=click.Choice(["table", "json", "html"]), default="table"
)
def show_pipelines(p, format):
    show_pipelines_commands.show_pipelines(p, format)


@cli.command()
@click.argument("portfolio-name")
@click.argument("product")
@click.argument("version")
def nuke_product_version(portfolio_name, product, version):
    portfolios.nuke_product_version(portfolio_name, product, version)


@cli.command()
@click.argument("branch-to-bootstrap")
@click.option("--source-provider", default="CodeCommit", envvar="SCM_SOURCE_PROVIDER")
@click.option(
    "--repository_name", default="ServiceCatalogFactory", envvar="SCM_REPOSITORY_NAME"
)
@click.option("--branch-name", default="master", envvar="SCM_BRANCH_NAME")
@click.option("--owner")
@click.option("--repo")
@click.option("--branch")
@click.option("--poll-for-source-changes", default=True)
@click.option("--webhook-secret")
@click.option("--scm-connection-arn", envvar="SCM_CONNECTION_ARN")
@click.option(
    "--scm-full-repository-id",
    default="ServiceCatalogFactory",
    envvar="SCM_FULL_REPOSITORY_ID",
)
@click.option("--scm-branch-name", default="main", envvar="SCM_BRANCH_NAME")
@click.option("--scm-bucket-name", envvar="SCM_BUCKET_NAME")
@click.option(
    "--scm-object-key", default="ServiceCatalogFactory.zip", envvar="SCM_OBJECT_KEY"
)
@click.option(
    "--create-repo/--no-create-repo", default=False, envvar="SCM_SHOULD_CREATE_REPO"
)
@click.option(
    "--should-validate/--no-should-validate",
    default=False,
    envvar="SCT_SHOULD_VALIDATE",
)
@click.option(
    "--custom-source-action-git-url", envvar="SCM_CUSTOM_SOURCE_ACTION_GIT_URL",
)
@click.option(
    "--custom-source-action-git-web-hook-ip-address",
    default="0.0.0.0/0",
    envvar="SCM_CUSTOM_SOURCE_ACTION_GIT_WEB_HOOK_IP_ADDRESS",
)
@click.option(
    "--custom-source-action-custom-action-type-version",
    default="CustomVersion1",
    envvar="SCM_CUSTOM_SOURCE_ACTION_CUSTOM_ACTION_TYPE_VERSION",
)
@click.option(
    "--custom-source-action-custom-action-type-provider",
    default="CustomProvider1",
    envvar="SCM_CUSTOM_SOURCE_ACTION_CUSTOM_ACTION_TYPE_PROVIDER",
)
def bootstrap_branch(
    branch_to_bootstrap,
    source_provider,
    repository_name,
    branch_name,
    owner,
    repo,
    branch,
    poll_for_source_changes,
    webhook_secret,
    scm_connection_arn,
    scm_full_repository_id,
    scm_branch_name,
    scm_bucket_name,
    scm_object_key,
    create_repo,
    should_validate,
    custom_source_action_git_url,
    custom_source_action_git_web_hook_ip_address,
    custom_source_action_custom_action_type_version,
    custom_source_action_custom_action_type_provider,
):
    args = dict(
        branch_to_bootstrap=branch_to_bootstrap,
        source_provider=source_provider,
        owner=None,
        repo=None,
        branch=None,
        poll_for_source_changes=poll_for_source_changes,
        webhook_secret=None,
        scm_connection_arn=None,
        scm_full_repository_id=None,
        scm_branch_name=None,
        scm_bucket_name=None,
        scm_object_key=None,
        create_repo=create_repo,
        should_validate=should_validate,
        custom_source_action_git_url=custom_source_action_git_url,
        custom_source_action_git_web_hook_ip_address=custom_source_action_git_web_hook_ip_address,
        custom_source_action_custom_action_type_version=custom_source_action_custom_action_type_version,
        custom_source_action_custom_action_type_provider=custom_source_action_custom_action_type_provider,
    )

    if source_provider == "CodeCommit":
        args.update(
            dict(
                repo=repository_name,
                branch=branch_name,
                poll_for_source_changes=poll_for_source_changes,
            )
        )

    elif source_provider == "GitHub":
        args.update(
            dict(
                owner=owner,
                repo=repo,
                branch=branch,
                poll_for_source_changes=poll_for_source_changes,
                webhook_secret=webhook_secret,
            )
        )

    elif source_provider == "CodeStarSourceConnection":
        args.update(
            dict(
                scm_connection_arn=scm_connection_arn,
                scm_full_repository_id=scm_full_repository_id,
                scm_branch_name=scm_branch_name,
            )
        )
    elif source_provider == "S3":
        args.update(
            dict(scm_bucket_name=scm_bucket_name, scm_object_key=scm_object_key,)
        )
    else:
        raise Exception(f"Unsupported source provider: {source_provider}")

    bootstrap_commands.bootstrap_branch(**args)


@cli.command()
@click.argument("secret-name")
@click.argument("oauth-token")
@click.argument("secret-token", default=False)
def add_secret(secret_name, oauth_token, secret_token):
    configuration_management.add_secret(secret_name, oauth_token, secret_token)


@cli.command()
@click.option("--source-provider", default="CodeCommit", envvar="SCM_SOURCE_PROVIDER")
@click.option(
    "--repository_name", default="ServiceCatalogFactory", envvar="SCM_REPOSITORY_NAME"
)
@click.option("--branch-name", default="master", envvar="SCM_BRANCH_NAME")
@click.option("--owner")
@click.option("--repo")
@click.option("--branch")
@click.option("--poll-for-source-changes", default=True)
@click.option("--webhook-secret")
@click.option("--scm-connection-arn", envvar="SCM_CONNECTION_ARN")
@click.option(
    "--scm-full-repository-id",
    default="ServiceCatalogFactory",
    envvar="SCM_FULL_REPOSITORY_ID",
)
@click.option("--scm-branch-name", default="main", envvar="SCM_BRANCH_NAME")
@click.option("--scm-bucket-name", envvar="SCM_BUCKET_NAME")
@click.option(
    "--scm-object-key", default="ServiceCatalogFactory.zip", envvar="SCM_OBJECT_KEY"
)
@click.option(
    "--create-repo/--no-create-repo", default=False, envvar="SCM_SHOULD_CREATE_REPO"
)
@click.option(
    "--should-validate/--no-should-validate",
    default=False,
    envvar="SCT_SHOULD_VALIDATE",
)
@click.option(
    "--custom-source-action-git-url", envvar="SCM_CUSTOM_SOURCE_ACTION_GIT_URL",
)
@click.option(
    "--custom-source-action-git-web-hook-ip-address",
    default="0.0.0.0/0",
    envvar="SCM_CUSTOM_SOURCE_ACTION_GIT_WEB_HOOK_IP_ADDRESS",
)
@click.option(
    "--custom-source-action-custom-action-type-version",
    default="CustomVersion1",
    envvar="SCM_CUSTOM_SOURCE_ACTION_CUSTOM_ACTION_TYPE_VERSION",
)
@click.option(
    "--custom-source-action-custom-action-type-provider",
    default="CustomProvider1",
    envvar="SCM_CUSTOM_SOURCE_ACTION_CUSTOM_ACTION_TYPE_PROVIDER",
)
def bootstrap(
    source_provider,
    repository_name,
    branch_name,
    owner,
    repo,
    branch,
    poll_for_source_changes,
    webhook_secret,
    scm_connection_arn,
    scm_full_repository_id,
    scm_branch_name,
    scm_bucket_name,
    scm_object_key,
    create_repo,
    should_validate,
    custom_source_action_git_url,
    custom_source_action_git_web_hook_ip_address,
    custom_source_action_custom_action_type_version,
    custom_source_action_custom_action_type_provider,
):
    args = get_parameters_for_bootstrap(
        branch,
        branch_name,
        create_repo,
        custom_source_action_custom_action_type_provider,
        custom_source_action_custom_action_type_version,
        custom_source_action_git_url,
        custom_source_action_git_web_hook_ip_address,
        owner,
        poll_for_source_changes,
        repo,
        repository_name,
        scm_branch_name,
        scm_bucket_name,
        scm_connection_arn,
        scm_full_repository_id,
        scm_object_key,
        should_validate,
        source_provider,
        webhook_secret,
    )

    bootstrap_commands.bootstrap(**args)


@cli.command()
@click.argument("secret-name")
@click.argument("oauth-token")
@click.argument("secret-token", default=False)
def add_secret(secret_name, oauth_token, secret_token):
    configuration_management.add_secret(secret_name, oauth_token, secret_token)


@cli.command()
@click.argument("name")
@click.option("--source-provider", default="CodeCommit", envvar="SCM_SOURCE_PROVIDER")
@click.option(
    "--repository_name",
    default="ServiceCatalogFactory-Secondary",
    envvar="SCM_REPOSITORY_NAME",
)
@click.option("--branch-name", default="main", envvar="SCM_BRANCH_NAME")
@click.option("--owner")
@click.option("--repo")
@click.option("--branch")
@click.option("--poll-for-source-changes", default=True)
@click.option("--webhook-secret")
@click.option("--scm-connection-arn", envvar="SCM_CONNECTION_ARN")
@click.option(
    "--scm-full-repository-id",
    default="ServiceCatalogFactory",
    envvar="SCM_FULL_REPOSITORY_ID",
)
@click.option("--scm-branch-name", default="main", envvar="SCM_BRANCH_NAME")
@click.option("--scm-bucket-name", envvar="SCM_BUCKET_NAME")
@click.option(
    "--scm-object-key", default="ServiceCatalogFactory.zip", envvar="SCM_OBJECT_KEY"
)
@click.option(
    "--create-repo/--no-create-repo", default=False, envvar="SCM_SHOULD_CREATE_REPO"
)
@click.option(
    "--should-validate/--no-should-validate",
    default=False,
    envvar="SCT_SHOULD_VALIDATE",
)
@click.option(
    "--custom-source-action-git-url", envvar="SCM_CUSTOM_SOURCE_ACTION_GIT_URL",
)
@click.option(
    "--custom-source-action-git-web-hook-ip-address",
    default="0.0.0.0/0",
    envvar="SCM_CUSTOM_SOURCE_ACTION_GIT_WEB_HOOK_IP_ADDRESS",
)
@click.option(
    "--custom-source-action-custom-action-type-version",
    default="CustomVersion1",
    envvar="SCM_CUSTOM_SOURCE_ACTION_CUSTOM_ACTION_TYPE_VERSION",
)
@click.option(
    "--custom-source-action-custom-action-type-provider",
    default="CustomProvider1",
    envvar="SCM_CUSTOM_SOURCE_ACTION_CUSTOM_ACTION_TYPE_PROVIDER",
)
def bootstrap_secondary(
    name,
    source_provider,
    repository_name,
    branch_name,
    owner,
    repo,
    branch,
    poll_for_source_changes,
    webhook_secret,
    scm_connection_arn,
    scm_full_repository_id,
    scm_branch_name,
    scm_bucket_name,
    scm_object_key,
    create_repo,
    should_validate,
    custom_source_action_git_url,
    custom_source_action_git_web_hook_ip_address,
    custom_source_action_custom_action_type_version,
    custom_source_action_custom_action_type_provider,
):
    args = get_parameters_for_bootstrap(
        branch,
        branch_name,
        create_repo,
        custom_source_action_custom_action_type_provider,
        custom_source_action_custom_action_type_version,
        custom_source_action_git_url,
        custom_source_action_git_web_hook_ip_address,
        owner,
        poll_for_source_changes,
        repo,
        repository_name,
        scm_branch_name,
        scm_bucket_name,
        scm_connection_arn,
        scm_full_repository_id,
        scm_object_key,
        should_validate,
        source_provider,
        webhook_secret,
    )

    bootstrap_commands.bootstrap(
        **args,
        bootstrap_type=constants.BOOTSTRAP_TYPE_SECONDARY,
        bootstrap_stack_name=name,
    )


def get_parameters_for_bootstrap(
    branch,
    branch_name,
    create_repo,
    custom_source_action_custom_action_type_provider,
    custom_source_action_custom_action_type_version,
    custom_source_action_git_url,
    custom_source_action_git_web_hook_ip_address,
    owner,
    poll_for_source_changes,
    repo,
    repository_name,
    scm_branch_name,
    scm_bucket_name,
    scm_connection_arn,
    scm_full_repository_id,
    scm_object_key,
    should_validate,
    source_provider,
    webhook_secret,
):
    args = dict(
        source_provider=source_provider,
        owner=None,
        repo=None,
        branch=None,
        poll_for_source_changes=poll_for_source_changes,
        webhook_secret=None,
        scm_connection_arn=None,
        scm_full_repository_id=None,
        scm_branch_name=None,
        scm_bucket_name=None,
        scm_object_key=None,
        create_repo=create_repo,
        should_validate=should_validate,
        custom_source_action_git_url=custom_source_action_git_url,
        custom_source_action_git_web_hook_ip_address=custom_source_action_git_web_hook_ip_address,
        custom_source_action_custom_action_type_version=custom_source_action_custom_action_type_version,
        custom_source_action_custom_action_type_provider=custom_source_action_custom_action_type_provider,
    )
    if source_provider == "CodeCommit":
        args.update(
            dict(
                repo=repository_name,
                branch=branch_name,
                poll_for_source_changes=poll_for_source_changes,
            )
        )

    elif source_provider == "GitHub":
        args.update(
            dict(
                owner=owner,
                repo=repo,
                branch=branch,
                poll_for_source_changes=poll_for_source_changes,
                webhook_secret=webhook_secret,
            )
        )

    elif source_provider == "CodeStarSourceConnection":
        args.update(
            dict(
                scm_connection_arn=scm_connection_arn,
                scm_full_repository_id=scm_full_repository_id,
                scm_branch_name=scm_branch_name,
            )
        )
    elif source_provider == "S3":
        args.update(
            dict(scm_bucket_name=scm_bucket_name, scm_object_key=scm_object_key,)
        )
    elif source_provider == "Custom":
        args.update(
            dict(
                custom_source_action_git_url=custom_source_action_git_url,
                branch=branch_name,
                custom_source_action_git_web_hook_ip_address=custom_source_action_git_web_hook_ip_address,
                custom_source_action_custom_action_type_version=custom_source_action_custom_action_type_version,
                custom_source_action_custom_action_type_provider=custom_source_action_custom_action_type_provider,
            )
        )
    else:
        raise Exception(f"Unsupported source provider: {source_provider}")
    return args


@cli.command()
@click.argument("complexity", default="simple")
@click.argument("p", type=click.Path(exists=True))
def seed(complexity, p):
    seed_commands.seed(complexity, p)


@cli.command()
def version():
    version_commands.version()


@cli.command()
@click.argument("p", type=click.Path(exists=True))
def upload_config(p):
    content = open(p, "r").read()
    config = yaml.safe_load(content)
    configuration_management.upload_config(config)


@cli.command()
@click.argument("stack-name")
def delete_stack_from_all_regions(stack_name):
    stacks.delete_stack_from_all_regions(stack_name)


@cli.command()
def list_resources():
    list_resources_commands.list_resources()


@cli.command()
@click.argument("f", type=click.File())
@click.argument("name")
@click.argument("portfolio_name", default=None)
def import_product_set(f, name, portfolio_name):
    portfolios.import_product_set(f, name, portfolio_name)


@cli.command()
@click.argument("portfolio_file_name")
@click.argument("portfolio_display_name")
@click.argument("product_definition", type=click.File())
def add_product_to_portfolio(
    portfolio_file_name, portfolio_display_name, product_definition
):
    portfolios.add_product_to_portfolio(
        portfolio_file_name,
        portfolio_display_name,
        yaml.safe_load(product_definition.read()),
    )


@cli.command()
@click.argument("portfolio_file_name")
@click.argument("portfolio_display_name")
@click.argument("product_name")
def remove_product_from_portfolio(
    portfolio_file_name, portfolio_display_name, product_name
):
    portfolios.remove_product_from_portfolio(
        portfolio_file_name, portfolio_display_name, product_name
    )


@cli.command()
@click.argument("portfolio_file_name")
@click.argument("portfolio_display_name")
@click.argument("product_name")
@click.argument("version_definition", type=click.File())
def add_version_to_product(
    portfolio_file_name, portfolio_display_name, product_name, version_definition
):
    portfolios.add_version_to_product(
        portfolio_file_name,
        portfolio_display_name,
        product_name,
        yaml.safe_load(version_definition),
    )


@cli.command()
@click.argument("portfolio_file_name")
@click.argument("portfolio_display_name")
@click.argument("product_name")
@click.argument("version_name")
def remove_version_from_product(
    portfolio_file_name, portfolio_display_name, product_name, version_name
):
    portfolios.remove_version_from_product(
        portfolio_file_name, portfolio_display_name, product_name, version_name
    )


@cli.command()
@click.argument("uid")
@click.argument("terraform_version")
@click.argument("tf_vars", nargs=-1)
def generate_terraform_template(uid, terraform_version, tf_vars):
    click.echo(portfolios.generate_terraform_template(uid, terraform_version, tf_vars))


@cli.command()
@click.argument("regions", nargs=-1)
def set_regions(regions):
    configuration_management.set_regions(regions)


@cli.command()
@click.argument("pipeline-name")
@click.argument("execution-id")
def print_source_directory(pipeline_name, execution_id):
    portfolios.print_source_directory(pipeline_name, execution_id)


@cli.command()
@click.argument("region")
@click.argument("name")
@click.argument("product-id")
@click.argument("description")
@click.argument("template-url")
def update_provisioned_product(region, name, product_id, description, template_url):
    portfolios.update_provisioned_product(
        region, name, product_id, description, template_url
    )


@cli.command()
@click.argument("provisioner_name")
@click.argument("provisioner_version")
@click.argument("product_name")
@click.argument("product_version")
@click.argument("p", type=click.Path(exists=True))
def generate_template(
    provisioner_name, provisioner_version, product_name, product_version, p
):
    click.echo(
        portfolios.generate_template(
            provisioner_name, provisioner_version, product_name, product_version, p
        )
    )


@cli.command()
@click.argument("pipeline-name")
@click.argument("pipeline-region")
@click.argument("codepipeline-id")
@click.argument("region")
@click.option("--source_path", default=".", envvar="SOURCE_PATH")
def create_or_update_provisioning_artifact_from_codepipeline_id(
    pipeline_name, pipeline_region, codepipeline_id, region, source_path
):
    cloudformation_servicecatalog_deploy_action.deploy(
        pipeline_name, pipeline_region, codepipeline_id, region, source_path
    )


@cli.command()
@click.argument("name")
@click.argument("value")
def set_config_value(name, value):
    management_commands.set_config_value(name, value)


@cli.command()
@click.argument("p", type=click.Path())
def generate_task_reference(p,):
    task_reference_commands.generate_task_reference(p)


if __name__ == "__main__":
    cli()
