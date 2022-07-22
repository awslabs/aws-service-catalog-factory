#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import glob
import yaml

from servicecatalog_factory.workflow.generic import create_generic_version_pipeline_task
from servicecatalog_factory import constants
from deepmerge import always_merger


def generate(path, item_collection_name, category, factory_version):
    tasks = list()
    for file_name in glob.glob(f"{path}/*.yaml"):
        file = yaml.safe_load(open(file_name, "r").read())
        for item in file.get(item_collection_name, []):
            name = item.get("Name")
            pipeline_mode = item.get("PipelineMode", constants.PIPELINE_MODE_DEFAULT)
            if pipeline_mode == constants.PIPELINE_MODE_SPILT:
                for version in item.get("Versions", []):
                    tasks.append(
                        create_task_for_split_pipeline(category, item, name, version)
                    )
                for version_file_name in glob.glob(f"{path}/{name}/Versions/*.yaml"):
                    version = yaml.safe_load(open(version_file_name, "r").read())
                    tasks.append(
                        create_task_for_split_pipeline(category, item, name, version)
                    )
            elif pipeline_mode == constants.PIPELINE_MODE_COMBINED:
                versions = list()
                for version in item.get("Versions", []):
                    versions.append(version)
                for version_file_name in glob.glob(f"{path}/{name}/Versions/*.yaml"):
                    version = yaml.safe_load(open(version_file_name, "r").read())
                    versions.append(version)
                tasks.append(
                    create_task_for_combined_pipeline(category, item, name, versions)
                )
            else:
                raise Exception(f"Unsupported pipeline_mode: {pipeline_mode}")
    return tasks


def create_task_for_combined_pipeline(category, item, name, versions):
    return create_generic_version_pipeline_task.CreateGenericCombinedPipelineTask(
        pipeline_type=constants.PIPELINE_MODE_COMBINED,
        category=category,
        name=name,
        item=item,
        versions=versions,
        options=item.get("Options", {}),
        stages=item.get("Stages", {}),
        tags=item.get("Tags", []),
    )


def create_task_for_split_pipeline(category, item, name, version):
    return create_generic_version_pipeline_task.CreateGenericCombinedPipelineTask(
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
    )
