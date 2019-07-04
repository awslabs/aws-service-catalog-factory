# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import traceback
from pathlib import Path
import jinja2
import luigi
from betterboto import client as betterboto_client
import logging
import json
import cfn_tools

from . import aws
from . import constants
from . import utils

logger = logging.getLogger(__file__)


class FactoryTask(luigi.Task):

    def params_for_results_display(self):
        return "Omitted"

    @property
    def resources(self):
        resources_for_this_task = {}

        if hasattr(self, 'region'):
            resources_for_this_task[self.region] = 1

        return resources_for_this_task


class CreatePortfolioTask(FactoryTask):
    region = luigi.Parameter()
    portfolio_group_name = luigi.Parameter()
    display_name = luigi.Parameter()
    description = luigi.Parameter(significant=False)
    provider_name = luigi.Parameter(significant=False)
    associations = luigi.ListParameter(significant=False, default=[])
    tags = luigi.ListParameter(default=[], significant=False)

    def params_for_results_display(self):
        return {
            "region": self.region,
            "portfolio_group_name": self.portfolio_group_name,
            "display_name": self.display_name,
        }

    def output(self):
        output_file = f"output/CreatePortfolioTask/{self.region}-{self.portfolio_group_name}-{self.display_name}.json"
        return luigi.LocalTarget(output_file)

    def run(self):
        logger_prefix = f"{self.region}-{self.portfolio_group_name}-{self.display_name}"
        with betterboto_client.ClientContextManager(
                'servicecatalog', region_name=self.region
        ) as service_catalog:
            generated_portfolio_name = f"{self.portfolio_group_name}-{self.display_name}"
            tags = []
            for t in self.tags:
                tags.append({
                    "Key": t.get('Key'),
                    "Value": t.get('Value'),
                })
            tags.append({"Key": "ServiceCatalogFactory:Actor", "Value": "Portfolio"})

            portfolio_detail = aws.get_or_create_portfolio(
                self.description,
                self.provider_name,
                generated_portfolio_name,
                tags,
                service_catalog
            )

        if portfolio_detail is None:
            raise Exception("portfolio_detail was not found or created")

        with self.output().open('w') as f:
            logger.info(f"{logger_prefix}: about to write! {portfolio_detail}")
            f.write(
                json.dumps(
                    portfolio_detail,
                    indent=4,
                    default=str,
                )
            )


class CreateProductTask(FactoryTask):
    uid = luigi.Parameter()
    region = luigi.Parameter()
    name = luigi.Parameter()
    owner = luigi.Parameter(significant=False)
    description = luigi.Parameter(significant=False)
    distributor = luigi.Parameter(significant=False)
    support_description = luigi.Parameter(significant=False)
    support_email = luigi.Parameter(significant=False)
    support_url = luigi.Parameter(significant=False)
    tags = luigi.ListParameter(default=[], significant=False)

    def params_for_results_display(self):
        return {
            "region": self.region,
            "uid": self.uid,
            "name": self.name,
        }

    def output(self):
        return luigi.LocalTarget(
            f"output/CreateProductTask/{self.region}-{self.name}.json"
        )

    def run(self):
        logger_prefix = f"{self.region}-{self.name}"
        with betterboto_client.ClientContextManager(
                'servicecatalog', region_name=self.region
        ) as service_catalog:
            tags = []
            for t in self.tags:
                tags.append({
                    "Key": t.get('Key'),
                    "Value": t.get('Value'),
                })
            tags.append({"Key": "ServiceCatalogFactory:Actor", "Value": "Product"})

            s3_bucket_name = aws.get_bucket_name()

            args = {
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
                },
                "Name": self.name,
                "Owner": self.owner,
                "Description": self.description,
                "Distributor": self.distributor,
                "SupportDescription": self.support_description,
                "SupportEmail": self.support_email,
                "SupportUrl": self.support_url,
                "Tags": tags
            }

            product_view_summary = aws.get_or_create_product(self.name, args, service_catalog)

            if product_view_summary is None:
                raise Exception(f"{logger_prefix}: did not find or create a product")

            product_view_summary['uid'] = self.uid
            with self.output().open('w') as f:
                logger.info(f"{logger_prefix}: about to write! {product_view_summary}")
                f.write(
                    json.dumps(
                        product_view_summary,
                        indent=4,
                        default=str,
                    )
                )


class AssociateProductWithPortfolioTask(FactoryTask):
    region = luigi.Parameter()
    portfolio_args = luigi.DictParameter()
    product_args = luigi.DictParameter()

    def params_for_results_display(self):
        return {
            "region": self.region,
            "portfolio": f"{self.portfolio_args.get('portfolio_group_name')}-{self.portfolio_args.get('display_name')}",
            "product": self.product_args.get('name'),
        }

    def output(self):
        return luigi.LocalTarget(
            f"output/AssociateProductWithPortfolioTask/"
            f"{self.region}"
            f"{self.product_args.get('name')}"
            f"_{self.portfolio_args.get('portfolio_group_name')}"
            f"_{self.portfolio_args.get('display_name')}.json"
        )

    def requires(self):
        return {
            'create_portfolio_task': CreatePortfolioTask(
                **self.portfolio_args
            ),
            'create_product_task': CreateProductTask(
                **self.product_args
            )
        }

    def run(self):
        logger_prefix = f"{self.region}-{self.portfolio_args.get('portfolio_group_name')}-{self.portfolio_args.get('display_name')}"
        portfolio = json.loads(self.input().get('create_portfolio_task').open('r').read())
        portfolio_id = portfolio.get('Id')
        product = json.loads(self.input().get('create_product_task').open('r').read())
        product_id = product.get('ProductId')
        with betterboto_client.ClientContextManager(
                'servicecatalog', region_name=self.region
        ) as service_catalog:
            logger.info(f"{logger_prefix}: Searching for existing association")

            aws.ensure_portfolio_association_for_product(portfolio_id, product_id, service_catalog)

            with self.output().open('w') as f:
                logger.info(f"{logger_prefix}: about to write!")
                f.write("{}")


class EnsureProductVersionDetailsCorrect(FactoryTask):
    region = luigi.Parameter()
    version = luigi.DictParameter()
    product_args = luigi.DictParameter()

    def params_for_results_display(self):
        return {
            "region": self.region,
            "version": self.version.get('Name'),
            "product": self.product_args.get('name'),
        }

    def output(self):
        return luigi.LocalTarget(
            f"output/EnsureProductVersionDetailsCorrect/"
            f"{self.region}_{self.product_args.get('name')}_{self.version.get('Name')}.json"
        )

    def requires(self):
        return CreateProductTask(
            **self.product_args
        )

    def run(self):
        product = json.loads(self.input().open('r').read())
        product_id = product.get('ProductId')
        version_name = self.version.get('Name')
        version_active = self.version.get('Active', True)

        with betterboto_client.ClientContextManager('servicecatalog', region_name=self.region) as service_catalog:
            response = service_catalog.list_provisioning_artifacts(
                ProductId=product_id
            )
            logger.info("Checking through: {}".format(response))
            for provisioning_artifact_detail in response.get('ProvisioningArtifactDetails', []):
                if provisioning_artifact_detail.get('Name') == version_name:
                    logger.info(f"Found matching: {version_name}: {provisioning_artifact_detail}")
                    if provisioning_artifact_detail.get('Active') != version_active:
                        logger.info(f"Active status needs to change for: {product.get('Name')} {version_name}")
                        service_catalog.update_provisioning_artifact(
                            ProductId=product_id,
                            ProvisioningArtifactId=provisioning_artifact_detail.get('Id'),
                            Active=version_active,
                        )

        with self.output().open('w') as f:
            f.write("{}")


class CreateVersionPipelineTemplateTask(FactoryTask):
    all_regions = luigi.ListParameter()
    version = luigi.DictParameter()
    product = luigi.DictParameter()

    products_args_by_region = luigi.DictParameter()

    def params_for_results_display(self):
        return {
            "version": self.version.get('Name'),
            "product": self.product.get('Name'),
        }

    def output(self):
        return luigi.LocalTarget(
            f"output/CreateVersionPipelineTemplateTask/"
            f"{self.product.get('Name')}_{self.version.get('Name')}.template.yaml"
        )

    def requires(self):
        create_products_tasks = {}
        for region, product_args_by_region in self.products_args_by_region.items():
            create_products_tasks[region] = CreateProductTask(
                **product_args_by_region
            )
        return {
            'create_products_tasks': create_products_tasks,
        }

    def run(self):
        logger_prefix = f"{self.product.get('Name')}-{self.version.get('Name')}"
        logger.info(f"{logger_prefix} - Getting product id")

        product_ids_by_region = {}
        friendly_uid = None
        for region, product_details_content in self.input().get('create_products_tasks').items():
            product_details = json.loads(product_details_content.open('r').read())
            product_ids_by_region[region] = product_details.get('ProductId')
            friendly_uid = product_details.get('uid')

        template = utils.ENV.get_template(constants.PRODUCT)

        rendered = template.render(
            friendly_uid=f"{friendly_uid}-{self.version.get('Name')}",
            version=self.version,
            product=self.product,
            Options=utils.merge(self.product.get('Options', {}), self.version.get('Options', {})),
            Source=utils.merge(self.product.get('Source', {}), self.version.get('Source', {})),
            ALL_REGIONS=self.all_regions,
            product_ids_by_region=product_ids_by_region,
        )
        rendered = jinja2.Template(rendered).render(
            friendly_uid=f"{friendly_uid}-{self.version.get('Name')}",
            version=self.version,
            product=self.product,
            Options=utils.merge(self.product.get('Options', {}), self.version.get('Options', {})),
            Source=utils.merge(self.product.get('Source', {}), self.version.get('Source', {})),
            ALL_REGIONS=self.all_regions,
            product_ids_by_region=product_ids_by_region,
        )

        with self.output().open('w') as output_file:
            output_file.write(rendered)


class CreateVersionPipelineTask(FactoryTask):
    all_regions = luigi.ListParameter()
    version = luigi.DictParameter()
    product = luigi.DictParameter()

    products_args_by_region = luigi.DictParameter()

    def output(self):
        return luigi.LocalTarget(
            f"output/CreateVersionPipelineTask/"
            f"{self.product.get('Name')}_{self.version.get('Name')}.template.yaml"
        )

    def requires(self):
        return CreateVersionPipelineTemplateTask(
            all_regions=self.all_regions,
            version=self.version,
            product=self.product,
            products_args_by_region=self.products_args_by_region,
        )

    def run(self):
        logger_prefix = f"{self.product.get('Name')}-{self.version.get('Name')}"
        template_contents = self.input().open('r').read()
        template = cfn_tools.load_yaml(template_contents)
        friendly_uid = template.get('Description')
        logger.info(f"{logger_prefix} creating the stack: {friendly_uid}")
        with betterboto_client.ClientContextManager('cloudformation') as cloudformation:
            response = cloudformation.create_or_update(
                StackName=friendly_uid,
                TemplateBody=template_contents,
            )

        with self.output().open('w') as f:
            f.write(json.dumps(
                response,
                indent=4,
                default=str,
            ))

        logger.info(f"{logger_prefix} - Finished")


def record_event(event_type, task, extra_event_data=None):
    task_type = task.__class__.__name__
    task_params = task.param_kwargs

    event = {
        "event_type": event_type,
        "task_type": task_type,
        "task_params": task_params,
        "params_for_results": task.params_for_results_display(),
    }
    if extra_event_data is not None:
        event.update(extra_event_data)

    with open(
            Path(constants.RESULTS_DIRECTORY) / event_type / f"{task_type}-{task.task_id}.json", 'w'
    ) as f:
        f.write(
            json.dumps(
                event,
                default=str,
                indent=4,
            )
        )


@luigi.Task.event_handler(luigi.Event.FAILURE)
def on_task_failure(task, exception):
    exception_details = {
        "exception_type": type(exception),
        "exception_stack_trace": traceback.format_exception(
            etype=type(exception),
            value=exception,
            tb=exception.__traceback__,
        )
    }
    record_event('failure', task, exception_details)


@luigi.Task.event_handler(luigi.Event.SUCCESS)
def on_task_success(task):
    record_event('success', task)


@luigi.Task.event_handler(luigi.Event.TIMEOUT)
def on_task_timeout(task):
    record_event('timeout', task)


@luigi.Task.event_handler(luigi.Event.PROCESS_FAILURE)
def on_task_process_failure(task):
    record_event('process_failure', task)


@luigi.Task.event_handler(luigi.Event.PROCESSING_TIME)
def on_task_processing_time(task, duration):
    record_event('processing_time', task, {"duration": duration})


@luigi.Task.event_handler(luigi.Event.BROKEN_TASK)
def on_task_broken_task(task):
    record_event('broken_task', task)
