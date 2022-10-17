#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import glob
import os

import yaml

from servicecatalog_factory.commands import task_reference_section_constants
from servicecatalog_factory import constants
from deepmerge import always_merger


def create_task_for_combined_pipeline(category, item, name, versions, additional_dependencies=[]):
    return dict(
        section_name=task_reference_section_constants.CREATE_GENERIC_COMBINED_PIPELINE_TASK,
        pipeline_type=constants.PIPELINE_MODE_COMBINED,
        category=category,
        name=name,
        item=item,
        versions=versions,
        options=item.get("Options", {}),
        stages=item.get("Stages", {}),
        tags=item.get("Tags", []),
        dependencies_by_reference=additional_dependencies,
    )


def create_task_for_split_pipeline(category, item, name, version, additional_dependencies=[]):
    return dict(
        section_name=task_reference_section_constants.CREATE_GENERIC_COMBINED_PIPELINE_TASK,
        pipeline_type=constants.PIPELINE_MODE_SPILT,
        category=category,
        name=name,
        item=item,
        versions=[version],
        options=always_merger.merge(
            item.get("Options", {}), version.get("Options", {})
        ),
        stages=always_merger.merge(item.get("Stages", {}), version.get("Stages", {})),
        tags=version.get("Tags", []) + item.get("Tags", []),
        dependencies_by_reference=additional_dependencies,
    )


def generate_tasks_for_generic_type(
        path, item_collection_name: str, category: str, factory_version: str, task_reference: dict,
):
    for file_name in glob.glob(f"{path}/*.yaml"):
        file = yaml.safe_load(open(file_name, "r").read())
        for item in file.get(item_collection_name, []):
            if category == "product":
                additional_dependencies = [
                    f"create-portfolio-{portfolio_name}-{constants.HOME_REGION}" for portfolio_name in item.get("Portfolios")
                ]
                generate_pipeline_task(category, item, path, task_reference, additional_dependencies)
            else:
                additional_dependencies = list()
                generate_pipeline_task(category, item, path, task_reference, additional_dependencies)


def generate_pipeline_task(category, item, path, task_reference, additional_dependencies=[]):
    name = item.get("Name")
    pipeline_mode = item.get("PipelineMode", constants.PIPELINE_MODE_DEFAULT)

    if pipeline_mode == constants.PIPELINE_MODE_SPILT:
        for version in item.get("Versions", []):
            task_reference[
                f"create-generic-split-pipeline-{category}-{name}-{version.get('Name')}"
            ] = create_task_for_split_pipeline(category, item, name, version, additional_dependencies)
        for version_file_name in glob.glob(f"{path}/{name}/Versions/*.yaml"):
            version = yaml.safe_load(open(version_file_name, "r").read())
            task_reference[
                f"create-generic-split-pipeline-{category}-{name}-{version.get('Name')}"
            ] = create_task_for_split_pipeline(category, item, name, version, additional_dependencies)
    elif pipeline_mode == constants.PIPELINE_MODE_COMBINED:
        versions = list()
        for version in item.get("Versions", []):
            versions.append(version)
        for version_file_name in glob.glob(f"{path}/{name}/Versions/*.yaml"):
            version = yaml.safe_load(open(version_file_name, "r").read())
            versions.append(version)

        task_reference[
            f"create-generic-combined-pipeline-{category}-{name}"
        ] = create_task_for_combined_pipeline(category, item, name, versions, additional_dependencies)

    else:
        raise Exception(f"Unsupported pipeline_mode: {pipeline_mode}")


# TODO add EnsureProductVersionDetailsCorrect
# TODO add CreateCodeRepoTask
def generate_tasks_for_portfolios(
        enabled_regions: list,
        path: str,
        item_collection_name: str,
        category: str,
        factory_version: str,
        task_reference: dict,
):
    for file_name in glob.glob(f"{path}/*.yaml"):
        file = yaml.safe_load(open(file_name, "r").read())
        # Add external defined products and versions
        p_name = os.path.basename(file_name)[0:-5]
        for portfolio_file in glob.glob(f"{path}/{p_name}/Portfolios/*"):
            if os.path.isdir(portfolio_file):
                portfolio_name = os.path.basename(portfolio_file)
                for external_product_file in glob.glob(f"{path}/{p_name}/Portfolios/{portfolio_name}/Products/*.yaml"):
                    product_name = os.path.basename(external_product_file)[0:-5]
                    for por in file[item_collection_name]:
                        if por.get("DisplayName") == portfolio_name:
                            pro = yaml.safe_load(open(external_product_file, 'r').read())
                            pro["Name"] = product_name
                            if not pro.get("Versions"):
                                pro["Versions"] = list()
                            por["Products"].append(pro)
                for external_version_file in glob.glob(
                    f"{path}/{p_name}/Portfolios/{portfolio_name}/Products/*/Versions/*.yaml"
                ):
                    version_name = os.path.basename(external_version_file)[0:-5]
                    product_name = external_version_file.split("/")[-3]
                    for por in file[item_collection_name]:
                        if por.get("DisplayName") == portfolio_name:
                            for pro in por.get("Products", []) + por.get("Components", []):
                                if pro.get("Name") == product_name:
                                    ver = yaml.safe_load(open(external_version_file, 'r').read())
                                    ver["Name"] = version_name
                                    pro["Versions"].append(ver)

        # READ THE portfolios FROM THE ROOT
        for item in file.get(item_collection_name, []):
            if item.get("PortfolioName"):
                portfolio_name = item.get("PortfolioName")
            else:
                portfolio_name = (
                        p_name + "-" + item.get("DisplayName")
                )
            for region in enabled_regions:
                create_portfolio_task_ref = f"create-portfolio-{portfolio_name}-{region}"
                associations = list()
                associations_dependencies_by_reference = list()

                if task_reference.get(create_portfolio_task_ref):
                    raise Exception(
                        f"Portfolio {portfolio_name} defined within {file_name} has already been declared")

                # CREATE PORTFOLIO
                task_reference[create_portfolio_task_ref] = dict(
                    task_reference=create_portfolio_task_ref,
                    section_name=task_reference_section_constants.CREATE_PORTFOLIO_TASK,
                    region=region,
                    dependencies_by_reference=[],
                    portfolio_name=portfolio_name,
                    description=item.get("Description"),
                    provider_name=item.get("ProviderName"),
                    tags=item.get("Tags", []),
                )

                # ADD ASSOCIATIONS FOR THE PORTFOLIO
                if item.get("Associations"):
                    task_reference[f"create-portfolio-{portfolio_name}-{region}-associations"] = dict(
                        task_reference=f"create-portfolio-{portfolio_name}-{region}-associations",
                        section_name=task_reference_section_constants.CREATE_PORTFOLIO_ASSOCIATIONS_TASK,
                        create_portfolio_task_ref=create_portfolio_task_ref,
                        dependencies_by_reference=[create_portfolio_task_ref],
                        region=region,
                        portfolio_name=portfolio_name,
                        associations=item.get("Associations"),
                        tags=item.get("Tags", []),
                    )

                # ADD PRODUCTS FOR THE PORTFOLIO
                for product in item.get("Components", []) + item.get("Products", []):
                    create_product_task_ref = f"create-product-{product.get('Name')}-{region}"
                    if task_reference.get(create_product_task_ref):
                        raise Exception(
                            f"Product {product.get('Name')} defined within {portfolio_name} {file_name} has already been declared")

                    # CREATE PRODUCT
                    task_reference[create_product_task_ref] = dict(
                        task_reference=create_product_task_ref,
                        section_name=task_reference_section_constants.CREATE_PRODUCT_TASK,
                        dependencies_by_reference=[],
                        region=region,
                        name=product.get("Name"),
                        owner=item.get("Owner"),
                        description=item.get("Description"),
                        distributor=item.get("Distributor"),
                        support_description=item.get("SupportDescription"),
                        support_email=item.get("SupportEmail"),
                        support_url=item.get("SupportUrl"),
                        tags=item.get("Tags", []),
                    )

                    # ASSOCIATE PRODUCT WITH PORTFOLIO
                    create_product_association_ref = f"create-product-association-{portfolio_name}-{product.get('Name')}-{region}"
                    task_reference[create_product_association_ref] = dict(
                        task_reference=create_product_association_ref,
                        section_name=task_reference_section_constants.CREATE_PRODUCT_ASSOCIATION_TASK,
                        create_product_task_ref=create_product_task_ref,
                        create_portfolio_task_ref=create_portfolio_task_ref,
                        dependencies_by_reference=[create_product_task_ref, create_portfolio_task_ref],
                        region=region,
                    )

                    # CREATE LAUNCH ROLE NAME CONSTRAINTS
                    if product.get("Constraints", {}).get("Launch", {}).get("LocalRoleName"):
                        associations.append(
                            dict(
                                portfolio_task_ref=create_portfolio_task_ref,
                                product_task_ref=create_product_task_ref,
                                local_role_name=product.get("Constraints", {}).get("Launch", {}).get("LocalRoleName"),
                            )
                        )
                        associations_dependencies_by_reference.append(create_product_association_ref)

                    if region == constants.HOME_REGION:
                        product_name = product.get("Name")
                        pipeline_mode = product.get("PipelineMode", constants.PIPELINE_MODE_DEFAULT)
                        if pipeline_mode == constants.PIPELINE_MODE_SPILT:
                            for version in product.get("Versions", []):
                                task_reference[
                                    f"create-generic-split-pipeline-product-{product_name}-{version.get('Name')}"
                                ] = create_task_for_split_pipeline("product", product, product_name, version, [create_product_task_ref])
                        elif pipeline_mode == constants.PIPELINE_MODE_COMBINED:
                            versions = list()
                            for version in product.get("Versions", []):
                                versions.append(version)
                            task_reference[
                                f"create-generic-combined-pipeline-product-{product_name}"
                            ] = create_task_for_combined_pipeline("product", product, product_name, versions, [create_product_task_ref])

                        else:
                            raise Exception(f"Unsupported pipeline_mode: {pipeline_mode}")


                # ADD LAUNCH ROLE NAME LAUNCH CONSTRAINT
                if associations:
                    launch_role_name_constraint_task_ref = f"create-launch-role-name-constraint-{portfolio_name}-{region}"
                    task_reference[launch_role_name_constraint_task_ref] = dict(
                        task_reference=launch_role_name_constraint_task_ref,
                        section_name=task_reference_section_constants.CREATE_LAUNCH_ROLE_NAME_CONSTRAINTS_TASK,
                        associations=associations,
                        dependencies_by_reference=associations_dependencies_by_reference,
                        region=region,
                    )

        # READ THE products FROM THE ROOT
        for item in file.get("Products", []) + file.get("Components", []):
            for region in enabled_regions:
                create_product_task_ref = f"create-product-{item.get('Name')}-{region}"

                if task_reference.get(create_product_task_ref):
                    raise Exception(
                        f"Product {item.get('Name')} defined within {file_name} has already been declared")

                # CREATE PRODUCT
                task_reference[create_product_task_ref] = dict(
                    task_reference=create_product_task_ref,
                    section_name=task_reference_section_constants.CREATE_PRODUCT_TASK,
                    dependencies_by_reference=[],
                    region=region,
                    name=item.get("Name"),
                    owner=item.get("Owner"),
                    description=item.get("Description"),
                    distributor=item.get("Distributor"),
                    support_description=item.get("SupportDescription"),
                    support_email=item.get("SupportEmail"),
                    support_url=item.get("SupportUrl"),
                    tags=item.get("Tags", []),
                )

                if region == constants.HOME_REGION:
                    product_name = item.get("Name")
                    pipeline_mode = item.get("PipelineMode", constants.PIPELINE_MODE_DEFAULT)
                    if pipeline_mode == constants.PIPELINE_MODE_SPILT:
                        for version in item.get("Versions", []):
                            task_reference[
                                f"create-generic-split-pipeline-product-{product_name}-{version.get('Name')}"
                            ] = create_task_for_split_pipeline("product", item, product_name, version,
                                                               [create_product_task_ref])
                    elif pipeline_mode == constants.PIPELINE_MODE_COMBINED:
                        versions = list()
                        for version in item.get("Versions", []):
                            versions.append(version)
                        task_reference[
                            f"create-generic-combined-pipeline-product-{product_name}"
                        ] = create_task_for_combined_pipeline("product", item, product_name, versions,
                                                              [create_product_task_ref])

                    else:
                        raise Exception(f"Unsupported pipeline_mode: {pipeline_mode}")

                for portfolio_name in item.get("Portfolios", []):
                    # GET PORTFOLIO
                    get_portfolio_task_ref = f"create-portfolio-{portfolio_name}-{region}"

                    # ASSOCIATE PRODUCT WITH PORTFOLIO
                    create_product_association_ref = f"create-product-association-{portfolio_name}-{item.get('Name')}-{region}"
                    task_reference[create_product_association_ref] = dict(
                        task_reference=create_product_association_ref,
                        section_name=task_reference_section_constants.CREATE_PRODUCT_ASSOCIATION_TASK,
                        create_product_task_ref=create_product_task_ref,
                        create_portfolio_task_ref=get_portfolio_task_ref,
                        dependencies_by_reference=[create_product_task_ref, get_portfolio_task_ref],
                        region=region,
                    )

                    # CREATE LAUNCH ROLE NAME CONSTRAINTS
                    if item.get("Constraints", {}).get("Launch", {}).get("LocalRoleName"):
                        local_role_name = item.get("Constraints", {}).get("Launch", {}).get("LocalRoleName")
                        launch_role_name_constraint_task_ref = f"create-launch-role-name-constraint-{portfolio_name}-{region}"
                        if not task_reference.get(launch_role_name_constraint_task_ref):
                            task_reference[launch_role_name_constraint_task_ref] = dict(
                                task_reference=launch_role_name_constraint_task_ref,
                                section_name=task_reference_section_constants.CREATE_LAUNCH_ROLE_NAME_CONSTRAINTS_TASK,
                                associations=list(),
                                dependencies_by_reference=list(),
                                region=region,
                            )
                        task_reference[launch_role_name_constraint_task_ref]["associations"].append(
                            dict(
                                portfolio_task_ref=get_portfolio_task_ref,
                                product_task_ref=create_product_task_ref,
                                local_role_name=local_role_name,
                            )
                        )
                        task_reference[launch_role_name_constraint_task_ref]["dependencies_by_reference"].append(
                            create_product_association_ref
                        )

    return task_reference


def generate_task_reference(p, enabled_regions, factory_version):
    task_reference = dict()

    portfolios_path = os.path.sep.join([p, "portfolios"])
    generate_tasks_for_portfolios(
        enabled_regions, portfolios_path, "Portfolios", "portfolio", factory_version, task_reference
    )

    products_path = os.path.sep.join([p, "products"])
    generate_tasks_for_generic_type(products_path, "Products", "product", factory_version, task_reference)

    stacks_path = os.path.sep.join([p, "stacks"])
    generate_tasks_for_generic_type(stacks_path, "Stacks", "stack", factory_version, task_reference)

    workspaces_path = os.path.sep.join([p, "workspaces"])
    generate_tasks_for_generic_type(workspaces_path, "Workspaces", "workspace", factory_version, task_reference)

    apps_path = os.path.sep.join([p, "apps"])
    generate_tasks_for_generic_type(apps_path, "Apps", "app", factory_version, task_reference)


    return task_reference
