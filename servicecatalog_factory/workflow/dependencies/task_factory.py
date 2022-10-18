#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import functools

from servicecatalog_factory.workflow.dependencies import section_names


def create(
    manifest_files_path, manifest_task_reference_file_path, parameters_to_use,
):
    section_name = parameters_to_use.get("section_name")
    minimum_common_parameters = dict(
        task_reference=parameters_to_use.get("task_reference"),
        manifest_files_path=manifest_files_path,
        # manifest_task_reference_file_path=manifest_task_reference_file_path,
        # manifest_files_path=manifest_files_path,
        dependencies_by_reference=parameters_to_use.get("dependencies_by_reference"),
    )

    status = parameters_to_use.get("status")
    if section_name == section_names.GET_BUCKET:
        if status == "terminated":
            raise Exception("NOT BUILT YET")
        else:
            from servicecatalog_factory.workflow.portfolios import get_bucket_task

            return get_bucket_task.GetBucketTask(**minimum_common_parameters,)

    elif section_name == section_names.CREATE_PRODUCT_TASK:
        if status == "terminated":
            raise Exception("NOT BUILT YET")
        else:
            from servicecatalog_factory.workflow.portfolios import create_product_task

            return create_product_task.CreateProductTask(
                **minimum_common_parameters,
                # uid=parameters_to_use.get("xxx"),
                get_bucket_task_ref=parameters_to_use.get("get_bucket_task_ref"),
                region=parameters_to_use.get("region"),
                name=parameters_to_use.get("name"),
                owner=parameters_to_use.get("owner"),
                description=parameters_to_use.get("description"),
                distributor=parameters_to_use.get("distributor"),
                support_description=parameters_to_use.get("support_description"),
                support_email=parameters_to_use.get("support_email"),
                support_url=parameters_to_use.get("support_url"),
                tags=parameters_to_use.get("tags"),
            )

    elif section_name == section_names.CREATE_PORTFOLIO_TASK:
        if status == "terminated":
            raise Exception("NOT BUILT YET")
        else:
            from servicecatalog_factory.workflow.portfolios import create_portfolio_task

            return create_portfolio_task.CreatePortfolioTask(
                **minimum_common_parameters,
                region=parameters_to_use.get("region"),
                portfolio_name=parameters_to_use.get("portfolio_name"),
                description=parameters_to_use.get("description"),
                provider_name=parameters_to_use.get("provider_name"),
                # portfolio_group_name =parameters_to_use.get("tags"),
                # display_name =parameters_to_use.get("tags"),
                tags=parameters_to_use.get("tags"),
            )

    elif section_name == section_names.CREATE_GENERIC_COMBINED_PIPELINE_TASK:
        if status == "terminated":
            raise Exception("NOT BUILT YET")
        else:
            from servicecatalog_factory.workflow.generic import (
                create_generic_version_pipeline_task,
            )

            return create_generic_version_pipeline_task.CreateGenericCombinedPipelineTask(
                **minimum_common_parameters,
                pipeline_type=parameters_to_use.get("pipeline_type"),
                category=parameters_to_use.get("category"),
                name=parameters_to_use.get("name"),
                item=parameters_to_use.get("item"),
                versions=parameters_to_use.get("versions"),
                options=parameters_to_use.get("options"),
                stages=parameters_to_use.get("stages"),
                tags=parameters_to_use.get("tags"),
            )

    elif section_name == section_names.CREATE_PORTFOLIO_ASSOCIATIONS_TASK:
        if status == "terminated":
            raise Exception("NOT BUILT YET")
        else:
            from servicecatalog_factory.workflow.portfolios import (
                create_portfolio_association_task,
            )

            factory_version = "XXX"  # TODO implement or remove

            return create_portfolio_association_task.CreatePortfolioAssociationTask(
                **minimum_common_parameters,
                region=parameters_to_use.get("region"),
                # portfolio_group_name =parameters_to_use.get("portfolio_group_name"),
                portfolio_name=parameters_to_use.get("portfolio_name"),
                # display_name =parameters_to_use.get("tags"),
                description=parameters_to_use.get("description"),
                provider_name=parameters_to_use.get("provider_name"),
                tags=parameters_to_use.get("tags"),
                associations=parameters_to_use.get("associations"),
                factory_version=factory_version,
            )

    elif section_name == section_names.CREATE_PRODUCT_ASSOCIATION_TASK:
        if status == "terminated":
            raise Exception("NOT BUILT YET")
        else:
            from servicecatalog_factory.workflow.portfolios import (
                associate_product_with_portfolio_task,
            )

            return associate_product_with_portfolio_task.AssociateProductWithPortfolioTask(
                **minimum_common_parameters,
                region=parameters_to_use.get("region"),
                portfolio_args=parameters_to_use.get("portfolio_args"),
                product_args=parameters_to_use.get("product_args"),
            )

    elif section_name == section_names.CREATE_LAUNCH_ROLE_NAME_CONSTRAINTS_TASK:
        if status == "terminated":
            raise Exception("NOT BUILT YET")
        else:
            from servicecatalog_factory.workflow.portfolios import (
                create_launch_role_name_constraints_task,
            )

            return create_launch_role_name_constraints_task.CreateLaunchRoleNameConstraintsTask(
                **minimum_common_parameters,
                # TODO implement
            )

    else:
        raise Exception(f"Unknown section_name: {section_name}")
