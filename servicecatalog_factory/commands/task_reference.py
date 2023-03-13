#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import glob
import os

import yaml

from servicecatalog_factory.workflow.dependencies import section_names
from servicecatalog_factory import constants
from deepmerge import always_merger

from servicecatalog_factory.workflow.dependencies import resources_factory


GET_BUCKET_TASK_REFERENCE = "get-bucket"


def create_task_for_combined_pipeline(
    task_reference,
    category,
    item,
    name,
    versions,
    additional_dependencies,
    stack_name="",
):
    return dict(
        status=item.get("Status"),
        section_name=section_names.CREATE_GENERIC_COMBINED_PIPELINE_TASK,
        region=constants.HOME_REGION,
        task_reference=task_reference,
        pipeline_type=constants.PIPELINE_MODE_COMBINED,
        category=category,
        name=name,
        item=item,
        versions=versions,
        options=item.get("Options", {}),
        stages=item.get("Stages", {}),
        tags=item.get("Tags", []),
        dependencies_by_reference=additional_dependencies,
        stack_name=stack_name,
    )


def create_task_for_split_pipeline(
    task_reference,
    category,
    item,
    name,
    version,
    additional_dependencies,
    stack_name="",
):
    return dict(
        section_name=section_names.CREATE_GENERIC_COMBINED_PIPELINE_TASK,
        status=version.get("Status"),
        region=constants.HOME_REGION,
        task_reference=task_reference,
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
        stack_name=stack_name,
    )


def generate_tasks_for_generic_type(
    enabled_regions,
    path,
    item_collection_name: str,
    category: str,
    factory_version: str,
    task_reference: dict,
):
    for file_name in glob.glob(f"{path}/*.yaml"):
        file = yaml.safe_load(open(file_name, "r").read())
        for item in file.get(item_collection_name, []):
            additional_dependencies = list()
            if category in ["product", "products"]:
                for portfolio in item.get("Portfolios"):
                    if isinstance(portfolio, str):
                        portfolio_name = portfolio
                    else:
                        portfolio_name = portfolio.get(
                            "PortfolioName",
                            f"{portfolio.get('PortfolioGroupName')}-{portfolio.get('DisplayName')}",
                        )
                    additional_dependencies.append(
                        f"create-portfolio-{portfolio_name}-{constants.HOME_REGION}"
                    )
                generate_tasks_for_product(
                    enabled_regions, file_name, item, "", task_reference,
                )
            generate_pipeline_task(
                category, item, path, task_reference, additional_dependencies
            )


def generate_pipeline_task(
    category, item, path, task_reference, additional_dependencies=[]
):
    name = item.get("Name")
    pipeline_mode = item.get("PipelineMode", constants.PIPELINE_MODE_DEFAULT)

    if pipeline_mode == constants.PIPELINE_MODE_SPILT:
        for version in item.get("Versions", []):
            task_ref = (
                f"create-generic-split-pipeline-{category}-{name}-{version.get('Name')}"
            )
            task_reference[task_ref] = create_task_for_split_pipeline(
                task_ref, category, item, name, version, additional_dependencies
            )
        for version_file_name in glob.glob(f"{path}/{name}/Versions/*.yaml"):
            version = yaml.safe_load(open(version_file_name, "r").read())
            task_ref = (
                f"create-generic-split-pipeline-{category}-{name}-{version.get('Name')}"
            )
            task_reference[task_ref] = create_task_for_split_pipeline(
                task_ref, category, item, name, version, additional_dependencies
            )
    elif pipeline_mode == constants.PIPELINE_MODE_COMBINED:
        versions = list()
        for version in item.get("Versions", []):
            versions.append(version)
        for version_file_name in glob.glob(f"{path}/{name}/Versions/*.yaml"):
            version = yaml.safe_load(open(version_file_name, "r").read())
            versions.append(version)
        task_ref = f"create-generic-combined-pipeline-{category}-{name}"
        task_reference[task_ref] = create_task_for_combined_pipeline(
            task_ref, category, item, name, versions, additional_dependencies
        )

    else:
        raise Exception(f"Unsupported pipeline_mode: {pipeline_mode}")


def generate_tasks_for_portfolios(
    enabled_regions: list,
    path: str,
    item_collection_name: str,
    category: str,
    factory_version: str,
    task_reference: dict,
):
    task_reference[GET_BUCKET_TASK_REFERENCE] = dict(
        task_reference=GET_BUCKET_TASK_REFERENCE,
        section_name=section_names.GET_BUCKET,
        dependencies_by_reference=[],
        region=constants.HOME_REGION,
    )

    for file_name in glob.glob(f"{path}/*.yaml"):
        file = yaml.safe_load(open(file_name, "r").read())
        # Add external defined products and versions
        p_name = os.path.basename(file_name)[0:-5]
        for portfolio_file in glob.glob(f"{path}/{p_name}/Portfolios/*"):
            if os.path.isdir(portfolio_file):
                portfolio_name = os.path.basename(portfolio_file)
                for product_name in os.listdir(
                    f"{path}/{p_name}/Portfolios/{portfolio_name}/Products/"
                ):
                    external_product_dir = f"{path}/{p_name}/Portfolios/{portfolio_name}/Products/{product_name}"

                    if not os.path.isdir(external_product_dir):
                        continue
                    for por in file[item_collection_name]:
                        if por.get("DisplayName") == portfolio_name:
                            pro = yaml.safe_load(
                                open(
                                    f"{external_product_dir}/{product_name}.yaml", "r"
                                ).read()
                            )
                            pro["Name"] = product_name
                            if not pro.get("Versions"):
                                pro["Versions"] = list()
                            if not por.get("Products"):
                                por["Products"] = list()
                            por["Products"].append(pro)
                for external_version_file in glob.glob(
                    f"{path}/{p_name}/Portfolios/{portfolio_name}/Products/*/Versions/*/*.yaml"
                ):
                    version_name = external_version_file.split("/")[-2]
                    product_name = external_version_file.split("/")[-4]
                    for por in file[item_collection_name]:
                        if por.get("DisplayName") == portfolio_name:
                            for pro in por.get("Products", []) + por.get(
                                "Components", []
                            ):
                                if pro.get("Name") == product_name:
                                    ver = yaml.safe_load(
                                        open(external_version_file, "r").read()
                                    )
                                    ver["Name"] = version_name
                                    pro["Versions"].append(ver)

        # READ THE portfolios FROM THE ROOT
        for item in file.get(item_collection_name, []):
            if item.get("PortfolioName"):
                portfolio_name = item.get("PortfolioName")
            else:
                portfolio_name = p_name + "-" + item.get("DisplayName")
            for region in enabled_regions:
                create_portfolio_task_ref = (
                    f"create-portfolio-{portfolio_name}-{region}"
                )
                launch_role_constraints = []
                launch_role_constraints_dependencies_by_reference = [
                    create_portfolio_task_ref,
                ]

                if task_reference.get(create_portfolio_task_ref):
                    raise Exception(
                        f"Portfolio {portfolio_name} defined within {file_name} has already been declared"
                    )

                # CREATE PORTFOLIO
                task_reference[create_portfolio_task_ref] = dict(
                    task_reference=create_portfolio_task_ref,
                    section_name=section_names.CREATE_PORTFOLIO_TASK,
                    region=region,
                    dependencies_by_reference=[],
                    portfolio_name=portfolio_name,
                    description=item.get("Description"),
                    provider_name=item.get("ProviderName"),
                    tags=item.get("Tags", []),
                )

                for tag_option in item.get("TagOptions", []):
                    tag_option_key = tag_option.get("Key")
                    tag_option_value = tag_option.get("Value")

                    create_tag_option_task_ref = f"create-tag-option-{region}-{tag_option_key}-{tag_option_value}"
                    if not task_reference.get(create_tag_option_task_ref):
                        task_reference[create_tag_option_task_ref] = dict(
                            task_reference=create_tag_option_task_ref,
                            section_name=section_names.CREATE_TAG_OPTION,
                            region=region,
                            dependencies_by_reference=[],
                            tag_option_key=tag_option_key,
                            tag_option_value=tag_option_value,
                        )

                    associate_tag_option_task_ref = f"associate-tag-option-{portfolio_name}-{region}--{tag_option_key}-{tag_option_value}"
                    task_reference[associate_tag_option_task_ref] = dict(
                        task_reference=associate_tag_option_task_ref,
                        section_name=section_names.ASSOCIATE_TAG_OPTION,
                        region=region,
                        dependencies_by_reference=[
                            create_portfolio_task_ref,
                            create_tag_option_task_ref,
                        ],
                        create_portfolio_task_ref=create_portfolio_task_ref,
                        create_tag_option_task_ref=create_tag_option_task_ref,
                    )

                # ADD ASSOCIATIONS FOR THE PORTFOLIO
                if item.get("Associations"):
                    task_reference[
                        f"create-portfolio-{portfolio_name}-{region}-associations"
                    ] = dict(
                        task_reference=f"create-portfolio-{portfolio_name}-{region}-associations",
                        section_name=section_names.CREATE_PORTFOLIO_ASSOCIATIONS_TASK,
                        create_portfolio_task_ref=create_portfolio_task_ref,
                        dependencies_by_reference=[create_portfolio_task_ref],
                        region=region,
                        portfolio_name=portfolio_name,
                        associations=item.get("Associations"),
                        tags=item.get("Tags", []),
                    )

                # ADD PRODUCTS FOR THE PORTFOLIO
                for product in item.get("Components", []) + item.get("Products", []):
                    create_product_task_ref = (
                        f"create-product-{product.get('Name')}-{region}"
                    )
                    if task_reference.get(create_product_task_ref):
                        raise Exception(
                            f"Product {product.get('Name')} defined within {portfolio_name} {file_name} has already been declared"
                        )

                    # CREATE PRODUCT
                    task_reference[create_product_task_ref] = dict(
                        task_reference=create_product_task_ref,
                        section_name=section_names.CREATE_PRODUCT_TASK,
                        get_bucket_task_ref=GET_BUCKET_TASK_REFERENCE,
                        dependencies_by_reference=[GET_BUCKET_TASK_REFERENCE],
                        region=region,
                        name=product.get("Name"),
                        owner=product.get("Owner"),
                        description=item.get("Description"),
                        distributor=product.get("Distributor"),
                        support_description=product.get("SupportDescription"),
                        support_email=product.get("SupportEmail"),
                        support_url=product.get("SupportUrl"),
                        tags=product.get("Tags", []) + item.get("Tags", []),
                    )

                    for tag_option in product.get("TagOptions", []):
                        tag_option_key = tag_option.get("Key")
                        tag_option_value = tag_option.get("Value")

                        create_tag_option_task_ref = f"create-tag-option-{region}-{tag_option_key}-{tag_option_value}"
                        if not task_reference.get(create_tag_option_task_ref):
                            task_reference[create_tag_option_task_ref] = dict(
                                task_reference=create_tag_option_task_ref,
                                section_name=section_names.CREATE_TAG_OPTION,
                                region=region,
                                dependencies_by_reference=[],
                                tag_option_key=tag_option_key,
                                tag_option_value=tag_option_value,
                            )

                        associate_tag_option_task_ref = f"associate-tag-option-{portfolio_name}-{product.get('Name')}-{region}--{tag_option_key}-{tag_option_value}"
                        task_reference[associate_tag_option_task_ref] = dict(
                            task_reference=associate_tag_option_task_ref,
                            section_name=section_names.ASSOCIATE_TAG_OPTION,
                            region=region,
                            dependencies_by_reference=[
                                create_product_task_ref,
                                create_tag_option_task_ref,
                            ],
                            create_product_task_ref=create_product_task_ref,
                            create_tag_option_task_ref=create_tag_option_task_ref,
                        )

                    # ASSOCIATE PRODUCT WITH PORTFOLIO
                    create_product_association_ref = f"create-product-association-{portfolio_name}-{product.get('Name')}-{region}"
                    task_reference[create_product_association_ref] = dict(
                        task_reference=create_product_association_ref,
                        section_name=section_names.CREATE_PRODUCT_ASSOCIATION_TASK,
                        create_product_task_ref=create_product_task_ref,
                        create_portfolio_task_ref=create_portfolio_task_ref,
                        dependencies_by_reference=[
                            create_product_task_ref,
                            create_portfolio_task_ref,
                        ],
                        region=region,
                    )

                    # CREATE LAUNCH ROLE NAME CONSTRAINTS
                    if (
                        product.get("Constraints", {})
                        .get("Launch", {})
                        .get("LocalRoleName")
                    ):
                        launch_role_constraints.append(
                            dict(
                                portfolio_task_ref=create_portfolio_task_ref,
                                product_task_ref=create_product_task_ref,
                                local_role_name=product.get("Constraints", {})
                                .get("Launch", {})
                                .get("LocalRoleName"),
                            )
                        )
                        launch_role_constraints_dependencies_by_reference.extend(
                            [create_product_association_ref, create_product_task_ref,]
                        )

                    for version in product.get("Versions", []):
                        # CREATE CODE REPO IF NEEDED
                        if (
                            version.get("Source", {})
                            .get("Configuration", {})
                            .get("Code")
                        ):
                            source = always_merger.merge({}, product.get("Source", {}))
                            always_merger.merge(source, version.get("Source", {}))
                            configuration = source.get("Configuration")
                            code = configuration.get("Code")
                            t_ref = f'{section_names.CREATE_CODE_REPO_TASK}-{configuration.get("RepositoryName")}-{configuration.get("BranchName")}'
                            task_reference[t_ref] = dict(
                                task_reference=t_ref,
                                section_name=section_names.CREATE_CODE_REPO_TASK,
                                dependencies_by_reference=[],
                                region=constants.HOME_REGION,
                                repository_name=configuration.get("RepositoryName"),
                                branch_name=configuration.get("BranchName"),
                                bucket=code.get("S3").get("Bucket"),
                                key=code.get("S3").get("Key"),
                            )

                        # ENSURE VERSIONS ARE UP TO DATE
                        task_ref = f"{section_names.ENSURE_PRODUCT_VERSION_DETAILS_CORRECT_TASK}-{region}-{product.get('Name')}-{version.get('Name')}"
                        task_reference[task_ref] = dict(
                            task_reference=task_ref,
                            section_name=section_names.ENSURE_PRODUCT_VERSION_DETAILS_CORRECT_TASK,
                            region=region,
                            version=version,
                            create_product_task_ref=create_product_task_ref,
                            dependencies_by_reference=[create_product_task_ref],
                        )

                    if region == constants.HOME_REGION:
                        product_name = product.get("Name")
                        pipeline_mode = product.get(
                            "PipelineMode", constants.PIPELINE_MODE_DEFAULT
                        )
                        if pipeline_mode == constants.PIPELINE_MODE_SPILT:
                            for version in product.get("Versions", []):
                                task_ref = f"create-generic-split-pipeline-product-{product_name}-{version.get('Name')}"
                                stack_name = f"{portfolio_name}-{product.get('Name')}-{version.get('Name')}"
                                task_reference[
                                    task_ref
                                ] = create_task_for_split_pipeline(
                                    task_ref,
                                    "product",
                                    product,
                                    product_name,
                                    version,
                                    [create_product_task_ref],
                                    stack_name,
                                )
                        elif pipeline_mode == constants.PIPELINE_MODE_COMBINED:
                            versions = list()
                            for version in product.get("Versions", []):
                                if version.get("Status") != constants.STATUS_TERMINATED:
                                    versions.append(version)
                            task_ref = f"create-generic-combined-pipeline-product-{product_name}"
                            stack_name = f"{portfolio_name}-{product.get('Name')}"
                            task_reference[
                                task_ref
                            ] = create_task_for_combined_pipeline(
                                task_ref,
                                "product",
                                product,
                                product_name,
                                versions,
                                [create_product_task_ref],
                                stack_name,
                            )

                        else:
                            raise Exception(
                                f"Unsupported pipeline_mode: {pipeline_mode}"
                            )

                # ADD LAUNCH ROLE NAME LAUNCH CONSTRAINT
                if launch_role_constraints:
                    launch_role_name_constraint_task_ref = (
                        f"create-launch-role-name-constraint-{portfolio_name}-{region}"
                    )
                    task_reference[launch_role_name_constraint_task_ref] = dict(
                        portfolio_name=portfolio_name,
                        task_reference=launch_role_name_constraint_task_ref,
                        section_name=section_names.CREATE_LAUNCH_ROLE_NAME_CONSTRAINTS_TASK,
                        launch_role_constraints=launch_role_constraints,
                        dependencies_by_reference=launch_role_constraints_dependencies_by_reference,
                        region=region,
                    )

        # READ THE products FROM THE ROOT
        for item in file.get("Products", []) + file.get("Components", []):
            generate_tasks_for_product(
                enabled_regions, file_name, item, p_name, task_reference,
            )

    return task_reference


def generate_tasks_for_product(
    enabled_regions, file_name, product_details, p_name, task_reference
):
    for region in enabled_regions:
        create_product_task_ref = (
            f"create-product-{product_details.get('Name')}-{region}"
        )

        if task_reference.get(create_product_task_ref):
            raise Exception(
                f"Product {product_details.get('Name')} defined within {file_name} has already been declared"
            )

        product_status = product_details.get("Status", constants.STATUS_DEFAULT)

        if product_status == constants.STATUS_ACTIVE:
            # CREATE PRODUCT
            task_reference[create_product_task_ref] = dict(
                task_reference=create_product_task_ref,
                section_name=section_names.CREATE_PRODUCT_TASK,
                get_bucket_task_ref=GET_BUCKET_TASK_REFERENCE,
                dependencies_by_reference=[GET_BUCKET_TASK_REFERENCE],
                region=region,
                name=product_details.get("Name"),
                owner=product_details.get("Owner"),
                description=product_details.get("Description"),
                distributor=product_details.get("Distributor"),
                support_description=product_details.get("SupportDescription"),
                support_email=product_details.get("SupportEmail"),
                support_url=product_details.get("SupportUrl"),
                tags=product_details.get("Tags", []),
            )

            for tag_option in product_details.get("TagOptions", []):
                tag_option_key = tag_option.get("Key")
                tag_option_value = tag_option.get("Value")

                create_tag_option_task_ref = (
                    f"create-tag-option-{region}-{tag_option_key}-{tag_option_value}"
                )
                if not task_reference.get(create_tag_option_task_ref):
                    task_reference[create_tag_option_task_ref] = dict(
                        task_reference=create_tag_option_task_ref,
                        section_name=section_names.CREATE_TAG_OPTION,
                        region=region,
                        dependencies_by_reference=[],
                        tag_option_key=tag_option_key,
                        tag_option_value=tag_option_value,
                    )

                associate_tag_option_task_ref = f"associate-tag-option-{product_details.get('Name')}-{region}--{tag_option_key}-{tag_option_value}"
                task_reference[associate_tag_option_task_ref] = dict(
                    task_reference=associate_tag_option_task_ref,
                    section_name=section_names.ASSOCIATE_TAG_OPTION,
                    region=region,
                    dependencies_by_reference=[
                        create_product_task_ref,
                        create_tag_option_task_ref,
                    ],
                    create_product_task_ref=create_product_task_ref,
                    create_tag_option_task_ref=create_tag_option_task_ref,
                )

            for version in product_details.get("Versions", []):
                # CREATE CODE REPO IF NEEDED
                if version.get("Source", {}).get("Configuration", {}).get("Code"):
                    source = always_merger.merge({}, product_details.get("Source", {}))
                    always_merger.merge(source, version.get("Source", {}))
                    configuration = source.get("Configuration")
                    code = configuration.get("Code")
                    t_ref = f'{section_names.CREATE_CODE_REPO_TASK}-{configuration.get("RepositoryName")}-{configuration.get("BranchName")}'
                    task_reference[t_ref] = dict(
                        task_reference=t_ref,
                        section_name=section_names.CREATE_CODE_REPO_TASK,
                        dependencies_by_reference=[],
                        region=constants.HOME_REGION,
                        repository_name=configuration.get("RepositoryName"),
                        branch_name=configuration.get("BranchName"),
                        bucket=code.get("S3").get("Bucket"),
                        key=code.get("S3").get("Key"),
                    )

                # ENSURE VERSIONS ARE UP TO DATE
                task_ref = f"{section_names.ENSURE_PRODUCT_VERSION_DETAILS_CORRECT_TASK}-{region}-{product_details.get('Name')}-{version.get('Name')}"
                task_reference[task_ref] = dict(
                    task_reference=task_ref,
                    section_name=section_names.ENSURE_PRODUCT_VERSION_DETAILS_CORRECT_TASK,
                    region=region,
                    version=version,
                    create_product_task_ref=create_product_task_ref,
                    dependencies_by_reference=[create_product_task_ref],
                )

            if region == constants.HOME_REGION:
                # create_portfolio_task_ref = (
                #     f"create-portfolio-{portfolio_name}-{region}"
                # )

                product_name = product_details.get("Name")
                pipeline_mode = product_details.get(
                    "PipelineMode", constants.PIPELINE_MODE_DEFAULT
                )
                if pipeline_mode == constants.PIPELINE_MODE_SPILT:
                    for version in product_details.get("Versions", []):
                        task_ref = f"create-generic-split-pipeline-product-{product_name}-{version.get('Name')}"
                        task_reference[task_ref] = create_task_for_split_pipeline(
                            task_ref,
                            "product",
                            product_details,
                            product_name,
                            version,
                            [create_product_task_ref],
                        )
                elif pipeline_mode == constants.PIPELINE_MODE_COMBINED:
                    versions = list()
                    for version in product_details.get("Versions", []):
                        versions.append(version)
                    task_ref = (
                        f"create-generic-combined-pipeline-product-{product_name}"
                    )
                    task_reference[task_ref] = create_task_for_combined_pipeline(
                        task_ref,
                        "product",
                        product_details,
                        product_name,
                        versions,
                        [create_product_task_ref],
                    )

                else:
                    raise Exception(f"Unsupported pipeline_mode: {pipeline_mode}")

            for portfolio_name_suffix in product_details.get("Portfolios", []):
                if isinstance(portfolio_name_suffix, str):
                    if p_name == "":
                        portfolio_name = portfolio_name_suffix
                    else:
                        portfolio_name = f"{p_name}-{portfolio_name_suffix}"
                else:
                    portfolio_name = portfolio_name_suffix.get(
                        "PortfolioName",
                        f"{portfolio_name_suffix.get('PortfolioGroupName')}-{portfolio_name_suffix.get('DisplayName')}",
                    )
                # GET PORTFOLIO
                get_portfolio_task_ref = f"create-portfolio-{portfolio_name}-{region}"

                # ASSOCIATE PRODUCT WITH PORTFOLIO
                create_product_association_ref = f"create-product-association-{portfolio_name}-{product_details.get('Name')}-{region}"
                task_reference[create_product_association_ref] = dict(
                    task_reference=create_product_association_ref,
                    section_name=section_names.CREATE_PRODUCT_ASSOCIATION_TASK,
                    create_product_task_ref=create_product_task_ref,
                    create_portfolio_task_ref=get_portfolio_task_ref,
                    dependencies_by_reference=[
                        create_product_task_ref,
                        get_portfolio_task_ref,
                    ],
                    region=region,
                )

                # CREATE LAUNCH ROLE NAME CONSTRAINTS
                if (
                    product_details.get("Constraints", {})
                    .get("Launch", {})
                    .get("LocalRoleName")
                ):
                    local_role_name = (
                        product_details.get("Constraints", {})
                        .get("Launch", {})
                        .get("LocalRoleName")
                    )
                    launch_role_name_constraint_task_ref = (
                        f"create-launch-role-name-constraint-{portfolio_name}-{region}"
                    )
                    if not task_reference.get(launch_role_name_constraint_task_ref):
                        task_reference[launch_role_name_constraint_task_ref] = dict(
                            portfolio_name=portfolio_name,
                            task_reference=launch_role_name_constraint_task_ref,
                            section_name=section_names.CREATE_LAUNCH_ROLE_NAME_CONSTRAINTS_TASK,
                            launch_role_constraints=[],
                            dependencies_by_reference=[],
                            region=region,
                        )
                    task_reference[launch_role_name_constraint_task_ref][
                        "launch_role_constraints"
                    ].append(
                        dict(
                            portfolio_task_ref=get_portfolio_task_ref,
                            product_task_ref=create_product_task_ref,
                            local_role_name=local_role_name,
                        )
                    )
                    task_reference[launch_role_name_constraint_task_ref][
                        "dependencies_by_reference"
                    ].extend(
                        [
                            # create_portfolio_task_ref,
                            f"create-portfolio-{portfolio_name}-{region}",
                            create_product_association_ref,
                            create_product_task_ref,
                        ]
                    )


def generate_task_reference(p, enabled_regions, factory_version):
    task_reference = dict()

    portfolios_path = os.path.sep.join([p, "portfolios"])
    generate_tasks_for_portfolios(
        enabled_regions,
        portfolios_path,
        "Portfolios",
        "portfolio",
        factory_version,
        task_reference,
    )

    products_path = os.path.sep.join([p, "products"])
    generate_tasks_for_generic_type(
        enabled_regions,
        products_path,
        "Products",
        "product",
        factory_version,
        task_reference,
    )

    stacks_path = os.path.sep.join([p, "stacks"])
    generate_tasks_for_generic_type(
        enabled_regions, stacks_path, "Stacks", "stack", factory_version, task_reference
    )

    workspaces_path = os.path.sep.join([p, "workspaces"])
    generate_tasks_for_generic_type(
        enabled_regions,
        workspaces_path,
        "Workspaces",
        "workspace",
        factory_version,
        task_reference,
    )

    apps_path = os.path.sep.join([p, "apps"])
    generate_tasks_for_generic_type(
        enabled_regions, apps_path, "Apps", "app", factory_version, task_reference
    )

    for _, task in task_reference.items():
        resources = resources_factory.create(task.get("section_name"), task)
        task["resources_required"] = resources

    return task_reference
