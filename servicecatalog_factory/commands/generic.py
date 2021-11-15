#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import glob
import yaml

from servicecatalog_factory.workflow.generic import create_generic_version_pipeline_task
from deepmerge import always_merger


def generate(path, item_collection_name, category, factory_version):
    tasks = list()
    for file_name in glob.glob(f"{path}/*.yaml"):
        file = yaml.safe_load(open(file_name, "r").read())
        for item in file.get(item_collection_name, []):
            for version in item.get("Versions", []):
                stages = always_merger.merge(
                    item.get("Stages", {}), version.get("Stages", {})
                )
                tasks.append(
                    create_generic_version_pipeline_task.CreateGenericVersionPipelineTask(
                        category=category,
                        name=item.get("Name"),
                        version=version.get("Name"),
                        source=always_merger.merge(
                            item.get("Source", {}), version.get("Source", {})
                        ),
                        options=always_merger.merge(
                            item.get("Options", {}), version.get("Options", {})
                        ),
                        stages=stages,
                    )
                )

    return tasks
