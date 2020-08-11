# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import yaml
from servicecatalog_factory import core
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
    core.validate(p)


@cli.command()
@click.argument("p", type=click.Path(exists=True))
@click.option("--branch-override")
def generate_via_luigi(p, branch_override=None):
    core.generate_via_luigi(p, branch_override)


@cli.command()
@click.argument("p", type=click.Path(exists=True))
@click.option("--format", "-f", type=click.Choice(["table", "json"]), default="table")
def show_pipelines(p, format):
    core.show_pipelines(p, format)


@cli.command()
@click.argument("p", type=click.Path(exists=True))
def deploy(p):
    core.deploy(p)


@cli.command()
@click.argument("portfolio-name")
@click.argument("product")
@click.argument("version")
def nuke_product_version(portfolio_name, product, version):
    core.nuke_product_version(portfolio_name, product, version)


@cli.command()
@click.argument("branch-name")
def bootstrap_branch(branch_name):
    core.bootstrap_branch(branch_name)


@cli.command()
@click.argument("secret-name")
@click.argument("oauth-token")
@click.argument("secret-token", default=False)
def add_secret(secret_name, oauth_token, secret_token):
    core.add_secret(secret_name, oauth_token, secret_token)


@cli.command()
def bootstrap():
    core.bootstrap()


@cli.command()
@click.argument("complexity", default="simple")
@click.argument("p", type=click.Path(exists=True))
def seed(complexity, p):
    core.seed(complexity, p)


@cli.command()
def version():
    core.version()


@cli.command()
@click.argument("p", type=click.Path(exists=True))
def upload_config(p):
    content = open(p, "r").read()
    config = yaml.safe_load(content)
    core.upload_config(config)


@cli.command()
@click.argument("p", type=click.Path(exists=True))
def fix_issues(p):
    core.fix_issues(p)


@cli.command()
@click.argument("stack-name")
def delete_stack_from_all_regions(stack_name):
    core.delete_stack_from_all_regions(stack_name)


@cli.command()
def list_resources():
    core.list_resources()


@cli.command()
@click.argument("f", type=click.File())
@click.argument("name")
@click.argument("portfolio_name", default=None)
def import_product_set(f, name, portfolio_name):
    core.import_product_set(f, name, portfolio_name)


@cli.command()
@click.argument("portfolio_file_name")
@click.argument("portfolio_display_name")
@click.argument("product_definition", type=click.File())
def add_product_to_portfolio(
    portfolio_file_name, portfolio_display_name, product_definition
):
    core.add_product_to_portfolio(
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
    core.remove_product_from_portfolio(
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
    core.add_version_to_product(
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
    core.remove_version_from_product(
        portfolio_file_name, portfolio_display_name, product_name, version_name
    )


@cli.command()
@click.argument("uid")
@click.argument("terraform_version")
@click.argument("tf_vars", nargs=-1)
def generate_terraform_template(uid, terraform_version, tf_vars):
    click.echo(core.generate_terraform_template(uid, terraform_version, tf_vars))


@cli.command()
@click.argument("regions", nargs=-1)
def set_regions(regions):
    core.set_regions(regions)


@cli.command()
@click.argument("p", type=click.Path(exists=True))
def generate_launch_constraints(p):
    core.generate_launch_constraints(p)


@cli.command()
@click.argument("pipeline-name")
@click.argument("execution-id")
@click.argument("artifact")
def print_source_directory(pipeline_name, execution_id, artifact):
    core.print_source_directory(pipeline_name, execution_id, artifact)


@cli.command()
@click.argument("region")
@click.argument("name")
@click.argument("product-id")
@click.argument("description")
@click.argument("template-url")
def update_provisioned_product(region, name, product_id, description, template_url):
    core.update_provisioned_product(region, name, product_id, description, template_url)


if __name__ == "__main__":
    cli()
