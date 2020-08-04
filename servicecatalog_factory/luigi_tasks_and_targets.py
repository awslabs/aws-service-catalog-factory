# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import traceback
from copy import deepcopy
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
from . import config

logger = logging.getLogger(__file__)


class FactoryTask(luigi.Task):
    def load_from_input(self, input_name):
        with self.input().get(input_name).open("r") as f:
            return json.loads(f.read())

    def info(self, message):
        logger.info(f"{self.uid}: {message}")

    def params_for_results_display(self):
        return "Omitted"

    def write_output(self, content):
        self.write_output_raw(json.dumps(content, indent=4, default=str,))

    def write_output_raw(self, content):
        with self.output().open("w") as f:
            f.write(content)

    def output(self):
        return luigi.LocalTarget(f"output/{self.uid}.json")

    @property
    def uid(self):
        return f"{self.__class__.__name__}/{self.node_id}"

    @property
    def node_id(self):
        return f"{self.__class__.__name__}_{'|'.join(self.params_for_results_display().values())}"

    @property
    def resources(self):
        resources_for_this_task = {}

        if hasattr(self, "region"):
            resources_for_this_task[self.region] = 1

        return resources_for_this_task


class GetBucketTask(FactoryTask):
    region = luigi.Parameter(default=constants.HOME_REGION)

    def params_for_results_display(self):
        return {
            "region": self.region,
        }

    def run(self):
        s3_bucket_url = None
        with betterboto_client.ClientContextManager(
            "cloudformation", region_name=self.region
        ) as cloudformation:
            response = cloudformation.describe_stacks(
                StackName=constants.BOOTSTRAP_STACK_NAME
            )
            assert (
                len(response.get("Stacks")) == 1
            ), "There should only be one stack with the name"
            outputs = response.get("Stacks")[0].get("Outputs")
            for output in outputs:
                if output.get("OutputKey") == "CatalogBucketName":
                    s3_bucket_url = output.get("OutputValue")
            assert s3_bucket_url is not None, "Could not find bucket"
            self.write_output({"s3_bucket_url": s3_bucket_url})


class CreatePortfolioTask(FactoryTask):
    region = luigi.Parameter()
    portfolio_group_name = luigi.Parameter()
    display_name = luigi.Parameter()
    description = luigi.Parameter(significant=False)
    provider_name = luigi.Parameter(significant=False)
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
            "servicecatalog", region_name=self.region
        ) as service_catalog:
            generated_portfolio_name = (
                f"{self.portfolio_group_name}-{self.display_name}"
            )
            tags = []
            for t in self.tags:
                tags.append(
                    {"Key": t.get("Key"), "Value": t.get("Value"),}
                )
            tags.append({"Key": "ServiceCatalogFactory:Actor", "Value": "Portfolio"})

            portfolio_detail = aws.get_or_create_portfolio(
                self.description,
                self.provider_name,
                generated_portfolio_name,
                tags,
                service_catalog,
            )

        if portfolio_detail is None:
            raise Exception("portfolio_detail was not found or created")

        with self.output().open("w") as f:
            logger.info(f"{logger_prefix}: about to write! {portfolio_detail}")
            f.write(json.dumps(portfolio_detail, indent=4, default=str,))


class CreatePortfolioAssociationTask(FactoryTask):
    region = luigi.Parameter()
    portfolio_group_name = luigi.Parameter()
    display_name = luigi.Parameter()
    description = luigi.Parameter(significant=False)
    provider_name = luigi.Parameter(significant=False)
    tags = luigi.ListParameter(default=[], significant=False)

    associations = luigi.ListParameter(significant=False, default=[])
    factory_version = luigi.Parameter()

    def requires(self):
        return CreatePortfolioTask(
            self.region,
            self.portfolio_group_name,
            self.display_name,
            self.description,
            self.provider_name,
            self.tags,
        )

    def params_for_results_display(self):
        return {
            "region": self.region,
            "portfolio_group_name": self.portfolio_group_name,
            "display_name": self.display_name,
        }

    def output(self):
        output_file = f"output/CreatePortfolioAssociationTask/{self.region}-{self.portfolio_group_name}-{self.display_name}.json"
        return luigi.LocalTarget(output_file)

    def run(self):
        with betterboto_client.ClientContextManager(
            "cloudformation", region_name=self.region
        ) as cloudformation:
            portfolio_details = json.loads(self.input().open("r").read())
            template = utils.ENV.get_template(constants.ASSOCIATIONS)
            rendered = template.render(
                FACTORY_VERSION=self.factory_version,
                portfolio={
                    "DisplayName": portfolio_details.get("DisplayName"),
                    "Associations": self.associations,
                },
                portfolio_id=portfolio_details.get("Id"),
            )
            stack_name = "-".join(
                [self.portfolio_group_name, self.display_name, "associations"]
            )
            cloudformation.create_or_update(
                StackName=stack_name, TemplateBody=rendered,
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

    def requires(self):
        return {"s3_bucket_url": GetBucketTask()}

    def output(self):
        return luigi.LocalTarget(
            f"output/CreateProductTask/{self.region}-{self.name}.json"
        )

    def run(self):
        logger_prefix = f"{self.region}-{self.name}"
        with betterboto_client.ClientContextManager(
            "servicecatalog", region_name=self.region
        ) as service_catalog:
            tags = []
            for t in self.tags:
                tags.append(
                    {"Key": t.get("Key"), "Value": t.get("Value"),}
                )
            tags.append({"Key": "ServiceCatalogFactory:Actor", "Value": "Product"})

            s3_bucket_name = self.load_from_input("s3_bucket_url").get("s3_bucket_url")

            args = {
                "ProductType": "CLOUD_FORMATION_TEMPLATE",
                "ProvisioningArtifactParameters": {
                    "Name": "-",
                    "Type": "CLOUD_FORMATION_TEMPLATE",
                    "Description": "Placeholder version, do not provision",
                    "Info": {
                        "LoadTemplateFromURL": "https://s3.amazonaws.com/{}/{}".format(
                            s3_bucket_name, "empty.template.yaml"
                        )
                    },
                },
                "Name": self.name,
                "Owner": self.owner,
                "Description": self.description,
                "Distributor": self.distributor,
                "SupportDescription": self.support_description,
                "SupportEmail": self.support_email,
                "SupportUrl": self.support_url,
                "Tags": tags,
            }

            product_view_summary = aws.get_or_create_product(
                self.name, args, service_catalog
            )

            if product_view_summary is None:
                raise Exception(f"{logger_prefix}: did not find or create a product")

            product_view_summary["uid"] = self.uid
            with self.output().open("w") as f:
                logger.info(f"{logger_prefix}: about to write! {product_view_summary}")
                f.write(json.dumps(product_view_summary, indent=4, default=str,))


class DeleteProductTask(FactoryTask):
    uid = luigi.Parameter()
    region = luigi.Parameter()
    name = luigi.Parameter()
    pipeline_mode = luigi.Parameter()

    def params_for_results_display(self):
        return {
            "region": self.region,
            "uid": self.uid,
            "name": self.name,
            "pipeline_mode": self.pipeline_mode,
        }

    def run(self):
        with betterboto_client.ClientContextManager(
            "servicecatalog", region_name=self.region
        ) as service_catalog:
            self.info(f"Looking for product to delete: {self.name}")
            search_products_as_admin_response = service_catalog.search_products_as_admin_single_page(
                Filters={"FullTextSearch": [self.name]}
            )
            found_product = False
            for product_view_details in search_products_as_admin_response.get(
                "ProductViewDetails"
            ):
                product_view_summary = product_view_details.get("ProductViewSummary")
                if product_view_summary.get("Name") == self.name:
                    found_product = True
                    product_id = product_view_summary.get("ProductId")
                    logger.info(f"Found product: {self.name}: {product_view_summary}")
                    break

            if found_product:
                with betterboto_client.ClientContextManager(
                    "cloudformation", region_name=self.region
                ) as cloudformation:
                    if self.pipeline_mode == constants.PIPELINE_MODE_SPILT:
                        self.delete_pipelines(
                            product_id, service_catalog, cloudformation
                        )
                    else:
                        self.info(f"Ensuring {self.name} is deleted")
                        cloudformation.ensure_deleted(StackName=self.name)

                self.delete_from_service_catalog(product_id, service_catalog)

                self.info(f"Finished Deleting {self.name}")
        self.write_output({"found_product": found_product})

    def delete_pipelines(self, product_id, service_catalog, cloudformation):
        list_versions_response = service_catalog.list_provisioning_artifacts_single_page(
            ProductId=product_id
        )
        version_names = [
            version["Name"]
            for version in list_versions_response.get("ProvisioningArtifactDetails", [])
        ]
        if len(version_names) > 0:
            self.info(
                f"Deleting Pipeline stacks for versions: {version_names} of {self.name}"
            )
            for version_name in version_names:
                self.info(f"Ensuring {self.uid}-{version_name} is deleted")
                cloudformation.ensure_deleted(StackName=f"{self.uid}-{version_name}")

    def delete_from_service_catalog(self, product_id, service_catalog):
        list_portfolios_response = service_catalog.list_portfolios_for_product_single_page(
            ProductId=product_id,
        )
        portfolio_ids = [
            portfolio_detail["Id"]
            for portfolio_detail in list_portfolios_response.get("PortfolioDetails", [])
        ]
        for portfolio_id in portfolio_ids:
            self.info(f"Disassociating {self.name} {product_id} from {portfolio_id}")
            service_catalog.disassociate_product_from_portfolio(
                ProductId=product_id, PortfolioId=portfolio_id
            )
        self.info(f"Deleting {self.name} {product_id} from Service Catalog")
        service_catalog.delete_product(Id=product_id,)


class AssociateProductWithPortfolioTask(FactoryTask):
    region = luigi.Parameter()
    portfolio_args = luigi.DictParameter()
    product_args = luigi.DictParameter()

    def params_for_results_display(self):
        return {
            "region": self.region,
            "portfolio": f"{self.portfolio_args.get('portfolio_group_name')}-{self.portfolio_args.get('display_name')}",
            "product": self.product_args.get("name"),
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
            "create_portfolio_task": CreatePortfolioTask(**self.portfolio_args),
            "create_product_task": CreateProductTask(**self.product_args),
        }

    def run(self):
        logger_prefix = f"{self.region}-{self.portfolio_args.get('portfolio_group_name')}-{self.portfolio_args.get('display_name')}"
        portfolio = json.loads(
            self.input().get("create_portfolio_task").open("r").read()
        )
        portfolio_id = portfolio.get("Id")
        product = json.loads(self.input().get("create_product_task").open("r").read())
        product_id = product.get("ProductId")
        with betterboto_client.ClientContextManager(
            "servicecatalog", region_name=self.region
        ) as service_catalog:
            logger.info(f"{logger_prefix}: Searching for existing association")

            aws.ensure_portfolio_association_for_product(
                portfolio_id, product_id, service_catalog
            )

            with self.output().open("w") as f:
                logger.info(f"{logger_prefix}: about to write!")
                f.write("{}")


class EnsureProductVersionDetailsCorrect(FactoryTask):
    region = luigi.Parameter()
    version = luigi.DictParameter()
    product_args = luigi.DictParameter()

    def params_for_results_display(self):
        return {
            "region": self.region,
            "version": self.version.get("Name"),
            "product": self.product_args.get("name"),
        }

    def output(self):
        return luigi.LocalTarget(
            f"output/EnsureProductVersionDetailsCorrect/"
            f"{self.region}_{self.product_args.get('name')}_{self.version.get('Name')}.json"
        )

    def requires(self):
        return CreateProductTask(**self.product_args)

    def run(self):
        product = json.loads(self.input().open("r").read())
        product_id = product.get("ProductId")
        version_name = self.version.get("Name")
        version_active = self.version.get("Active", True)

        with betterboto_client.ClientContextManager(
            "servicecatalog", region_name=self.region
        ) as service_catalog:
            response = service_catalog.list_provisioning_artifacts(ProductId=product_id)
            logger.info("Checking through: {}".format(response))
            for provisioning_artifact_detail in response.get(
                "ProvisioningArtifactDetails", []
            ):
                if provisioning_artifact_detail.get("Name") == version_name:
                    logger.info(
                        f"Found matching: {version_name}: {provisioning_artifact_detail}"
                    )
                    if provisioning_artifact_detail.get("Active") != version_active:
                        logger.info(
                            f"Active status needs to change for: {product.get('Name')} {version_name}"
                        )
                        service_catalog.update_provisioning_artifact(
                            ProductId=product_id,
                            ProvisioningArtifactId=provisioning_artifact_detail.get(
                                "Id"
                            ),
                            Active=version_active,
                        )

        with self.output().open("w") as f:
            f.write("{}")


class CreateVersionPipelineTemplateTask(FactoryTask):
    all_regions = luigi.ListParameter()
    version = luigi.DictParameter()
    product = luigi.DictParameter()

    provisioner = luigi.DictParameter()
    factory_version = luigi.Parameter()

    products_args_by_region = luigi.DictParameter()

    tags = luigi.ListParameter()

    def params_for_results_display(self):
        return {
            "version": self.version.get("Name"),
            "product": self.product.get("Name"),
            "type": self.provisioner.get("Type"),
        }

    def output(self):
        return luigi.LocalTarget(
            f"output/CreateVersionPipelineTemplateTask/"
            f"{self.product.get('Name')}_{self.version.get('Name')}.template.yaml"
        )

    def requires(self):
        create_products_tasks = {}
        for region, product_args_by_region in self.products_args_by_region.items():
            create_products_tasks[region] = CreateProductTask(**product_args_by_region)
        return {
            "create_products_tasks": create_products_tasks,
        }

    def run(self):
        logger_prefix = f"{self.product.get('Name')}-{self.version.get('Name')}"
        logger.info(f"{logger_prefix} - Getting product id")

        product_ids_by_region = {}
        friendly_uid = None

        tags = []
        for tag in self.tags:
            tags.append(
                {"Key": tag.get("Key"), "Value": tag.get("Value"),}
            )

        for region, product_details_content in (
            self.input().get("create_products_tasks").items()
        ):
            product_details = json.loads(product_details_content.open("r").read())
            product_ids_by_region[region] = product_details.get("ProductId")
            friendly_uid = product_details.get("uid")

        if self.provisioner.get("Type") == "CloudFormation":
            template = utils.ENV.get_template(constants.PRODUCT_CLOUDFORMATION)
            rendered = template.render(
                friendly_uid=f"{friendly_uid}-{self.version.get('Name')}",
                version=self.version,
                product=self.product,
                template_format=self.provisioner.get("Format", "yaml"),
                Options=utils.merge(
                    self.product.get("Options", {}), self.version.get("Options", {})
                ),
                Source=utils.merge(
                    self.product.get("Source", {}), self.version.get("Source", {})
                ),
                ALL_REGIONS=self.all_regions,
                product_ids_by_region=product_ids_by_region,
                FACTORY_VERSION=self.factory_version,
                tags=tags,
            )
            rendered = jinja2.Template(rendered).render(
                friendly_uid=f"{friendly_uid}-{self.version.get('Name')}",
                version=self.version,
                product=self.product,
                Options=utils.merge(
                    self.product.get("Options", {}), self.version.get("Options", {})
                ),
                Source=utils.merge(
                    self.product.get("Source", {}), self.version.get("Source", {})
                ),
                ALL_REGIONS=self.all_regions,
                product_ids_by_region=product_ids_by_region,
            )

        elif self.provisioner.get("Type") == "Terraform":
            template = utils.ENV.get_template(constants.PRODUCT_TERRAFORM)
            rendered = template.render(
                friendly_uid=f"{friendly_uid}-{self.version.get('Name')}",
                version=self.version,
                product=self.product,
                Options=utils.merge(
                    self.product.get("Options", {}), self.version.get("Options", {})
                ),
                Source=utils.merge(
                    self.product.get("Source", {}), self.version.get("Source", {})
                ),
                ALL_REGIONS=self.all_regions,
                product_ids_by_region=product_ids_by_region,
                TF_VARS=" ".join(self.provisioner.get("TFVars", [])),
                FACTORY_VERSION=self.factory_version,
                tags=tags,
            )
            rendered = jinja2.Template(rendered).render(
                friendly_uid=f"{friendly_uid}-{self.version.get('Name')}",
                version=self.version,
                product=self.product,
                Options=utils.merge(
                    self.product.get("Options", {}), self.version.get("Options", {})
                ),
                Source=utils.merge(
                    self.product.get("Source", {}), self.version.get("Source", {})
                ),
                ALL_REGIONS=self.all_regions,
                product_ids_by_region=product_ids_by_region,
                TF_VARS=" ".join(self.provisioner.get("TFVars", [])),
                FACTORY_VERSION=self.factory_version,
            )

        else:
            raise Exception(f"Unknown type: {self.type}")

        with self.output().open("w") as output_file:
            output_file.write(rendered)


class CreateVersionPipelineTask(FactoryTask):
    all_regions = luigi.ListParameter()
    version = luigi.DictParameter()
    product = luigi.DictParameter()

    provisioner = luigi.DictParameter()

    products_args_by_region = luigi.DictParameter()

    factory_version = luigi.Parameter()
    region = luigi.Parameter()

    tags = luigi.ListParameter()

    def params_for_results_display(self):
        return {
            "version": self.version.get("Name"),
            "product": self.product.get("Name"),
        }

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
            provisioner=self.provisioner,
            products_args_by_region=self.products_args_by_region,
            factory_version=self.factory_version,
            tags=self.tags,
        )

    def run(self):
        template_contents = self.input().open("r").read()
        template = cfn_tools.load_yaml(template_contents)
        friendly_uid = template.get("Description").split("\n")[0]
        self.info(f"creating the stack: {friendly_uid}")
        tags = []
        for tag in self.tags:
            tags.append(
                {"Key": tag.get("Key"), "Value": tag.get("Value"),}
            )
        with betterboto_client.ClientContextManager("cloudformation") as cloudformation:
            if self.provisioner.get("Type") == "CloudFormation":
                response = cloudformation.create_or_update(
                    StackName=friendly_uid, TemplateBody=template_contents, Tags=tags,
                )
            elif self.provisioner.get("Type") == "Terraform":
                response = cloudformation.create_or_update(
                    StackName=friendly_uid,
                    TemplateBody=template_contents,
                    Parameters=[
                        {
                            "ParameterKey": "Version",
                            "ParameterValue": self.factory_version,
                            "UsePreviousValue": False,
                        },
                    ],
                    Tags=tags,
                )

        with self.output().open("w") as f:
            f.write(json.dumps(response, indent=4, default=str,))

        self.info(f"Finished")


class DeleteAVersionTask(FactoryTask):
    product_args = luigi.DictParameter()
    version = luigi.Parameter()

    @property
    def resources(self):
        return {self.product_args.get("region"): 1}

    def params_for_results_display(self):
        return {
            "uid": self.product_args.get("uid"),
            "region": self.product_args.get("region"),
            "name": self.product_args.get("name"),
            "version": self.version,
        }

    def requires(self):
        return {"create_product": CreateProductTask(**self.product_args)}

    def run(self):
        product = self.load_from_input("create_product")
        product_id = product.get("ProductId")
        self.info(f"Starting delete of {product_id} {self.version}")
        region = self.product_args.get("region")
        found = False
        with betterboto_client.ClientContextManager(
            "servicecatalog", region_name=region
        ) as servicecatalog:
            provisioning_artifact_details = servicecatalog.list_provisioning_artifacts_single_page(
                ProductId=product_id,
            ).get(
                "ProvisioningArtifactDetails", []
            )

            for provisioning_artifact_detail in provisioning_artifact_details:
                if provisioning_artifact_detail.get("Name") == self.version:
                    provisioning_artifact_id = provisioning_artifact_detail.get("Id")
                    self.info(f"Found version: {provisioning_artifact_id}, deleting it")
                    servicecatalog.delete_provisioning_artifact(
                        ProductId=product_id,
                        ProvisioningArtifactId=provisioning_artifact_id,
                    )
                    found = True
                    break

        if not found:
            self.info("Did not find product version to delete")

        product["found"] = found

        with betterboto_client.ClientContextManager(
            "cloudformation", region_name=region
        ) as cloudformation:
            cloudformation.ensure_deleted(
                StackName=f"{product.get('uid')}-{self.version}"
            )

        self.write_output(product)


class CreateCombinedProductPipelineTemplateTask(FactoryTask):
    all_regions = luigi.ListParameter()
    product = luigi.DictParameter()
    products_args_by_region = luigi.DictParameter()
    factory_version = luigi.Parameter()

    def params_for_results_display(self):
        return {
            "product": self.product.get("Name"),
        }

    def output(self):
        return luigi.LocalTarget(
            f"output/CreateCombinedProductPipelineTemplateTask/"
            f"{self.product.get('Name')}.template.yaml"
        )

    def requires(self):
        create_products_tasks = {}
        for region, product_args_by_region in self.products_args_by_region.items():
            create_products_tasks[region] = CreateProductTask(**product_args_by_region)
        return {
            "create_products_tasks": create_products_tasks,
        }

    def run(self):
        product_ids_by_region = {}
        friendly_uid = None

        for region, product_details_content in (
            self.input().get("create_products_tasks").items()
        ):
            product_details = json.loads(product_details_content.open("r").read())
            product_ids_by_region[region] = product_details.get("ProductId")
            friendly_uid = product_details.get("uid")

        provisioner_type = self.product.get("Provisioner", {}).get(
            "Type", constants.PROVISIONERS_DEFAULT
        )
        template_format = self.product.get("Provisioner", {}).get(
            "Format", constants.TEMPLATE_FORMATS_DEFAULT
        )

        versions = list()
        for version in self.product.get("Versions"):
            if (
                version.get("Status", constants.STATUS_DEFAULT)
                == constants.STATUS_ACTIVE
            ):
                versions.append(version)

        if provisioner_type == constants.PROVISIONERS_CLOUDFORMATION:
            template = utils.ENV.get_template(constants.PRODUCT_COMBINED_CLOUDFORMATION)
            rendered = template.render(
                friendly_uid=friendly_uid,
                product=self.product,
                template_format=template_format,
                Options=self.product.get("Options", {}),
                Versions=versions,
                ALL_REGIONS=self.all_regions,
                product_ids_by_region=product_ids_by_region,
                FACTORY_VERSION=self.factory_version,
                VERSION=config.get_stack_version(),
                tags=self.product.get("Tags"),
            )
            rendered = jinja2.Template(rendered).render(
                friendly_uid=friendly_uid,
                product=self.product,
                Options=self.product.get("Options", {}),
                Versions=versions,
                ALL_REGIONS=self.all_regions,
                product_ids_by_region=product_ids_by_region,
            )

        else:
            raise Exception(f"Unknown/unsupported provisioner type: {provisioner_type}")

        self.write_output_raw(rendered)


class CreateCombinedProductPipelineTask(FactoryTask):
    all_regions = luigi.ListParameter()
    product = luigi.DictParameter()
    products_args_by_region = luigi.DictParameter()
    factory_version = luigi.Parameter()

    def params_for_results_display(self):
        return {
            "product": self.product.get("Name"),
        }

    def requires(self):
        return CreateCombinedProductPipelineTemplateTask(
            all_regions=self.all_regions,
            product=self.product,
            products_args_by_region=self.products_args_by_region,
            factory_version=self.factory_version,
        )

    def run(self):
        template_contents = self.input().open("r").read()
        template = cfn_tools.load_yaml(template_contents)
        friendly_uid = template.get("Description").split("\n")[0]
        self.info(f"creating the stack: {friendly_uid}")
        tags = []

        for tag in self.product.get("Tags"):
            tags.append(
                {"Key": tag.get("Key"), "Value": tag.get("Value"),}
            )
        provisioner = self.product.get("Provisioner", {}).get(
            "Type", constants.PROVISIONERS_DEFAULT
        )
        with betterboto_client.ClientContextManager("cloudformation") as cloudformation:
            if provisioner == constants.PROVISIONERS_CLOUDFORMATION:
                response = cloudformation.create_or_update(
                    StackName=friendly_uid, TemplateBody=template_contents, Tags=tags,
                )
            else:
                raise Exception(f"Unknown/unsupported provisioner: {provisioner}")

        self.info(f"Finished")
        self.write_output(response)


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
        Path(constants.RESULTS_DIRECTORY)
        / event_type
        / f"{task_type}-{task.task_id}.json",
        "w",
    ) as f:
        f.write(json.dumps(event, default=str, indent=4,))


@luigi.Task.event_handler(luigi.Event.FAILURE)
def on_task_failure(task, exception):
    exception_details = {
        "exception_type": type(exception),
        "exception_stack_trace": traceback.format_exception(
            etype=type(exception), value=exception, tb=exception.__traceback__,
        ),
    }
    record_event("failure", task, exception_details)


@luigi.Task.event_handler(luigi.Event.SUCCESS)
def on_task_success(task):
    record_event("success", task)


@luigi.Task.event_handler(luigi.Event.TIMEOUT)
def on_task_timeout(task):
    record_event("timeout", task)


@luigi.Task.event_handler(luigi.Event.PROCESS_FAILURE)
def on_task_process_failure(task):
    record_event("process_failure", task)


@luigi.Task.event_handler(luigi.Event.PROCESSING_TIME)
def on_task_processing_time(task, duration):
    record_event("processing_time", task, {"duration": duration})


@luigi.Task.event_handler(luigi.Event.BROKEN_TASK)
def on_task_broken_task(task):
    record_event("broken_task", task)
