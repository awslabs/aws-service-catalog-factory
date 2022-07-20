#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import os
from servicecatalog_factory import constants

from betterboto import client as betterboto_client
import yaml


def extract_from_ssm(target):
    with betterboto_client.ClientContextManager("ssm") as ssm:
        paginator = ssm.get_paginator("get_parameters_by_path")
        for pipeline_type in ["stacks", "workspaces", "apps", "products"]:
            pipelines = dict()
            for page in paginator.paginate(
                Path=f"{constants.SERVICE_CATALOG_FACTORY_PIPELINES}/{pipeline_type}",
                Recursive=True,
            ):
                for parameter in page.get("Parameters", ""):
                    name = (
                        parameter.get("Name")
                        .replace(constants.SERVICE_CATALOG_FACTORY_PIPELINES, "")
                        .split("/")
                    )
                    file_name = name[2]
                    if pipelines.get(file_name) is None:
                        pipelines[file_name] = dict(Schema="factory-2019-04-01")
                        pipelines[file_name][pipeline_type.title()] = list()
                    item = yaml.safe_load(parameter.get("Value"))
                    item["Name"] = name[3]
                    pipelines[file_name][pipeline_type.title()].append(item)
            for file_name, items in pipelines.items():
                target_path = os.path.sep.join([target, pipeline_type])
                if not os.path.exists(target_path):
                    os.makedirs(target_path)
                open(os.path.sep.join([target_path, f"{file_name}.yaml"]), "w").write(
                    yaml.safe_dump(items)
                )

        for page in paginator.paginate(
            Path=f"{constants.SERVICE_CATALOG_FACTORY_PIPELINES}/portfolios",
            Recursive=True,
        ):
            pipelines = dict()
            for parameter in page.get("Parameters", ""):
                name = (
                    parameter.get("Name")
                    .replace(constants.SERVICE_CATALOG_FACTORY_PIPELINES, "")
                    .split("/")
                )
                file_name = name[2]
                item_type = name[3]
                item_name = name[4]

                if pipelines.get(file_name) is None:
                    pipelines[file_name] = dict(
                        Schema="factory-2019-04-01", Products=list(), Portfolios=list()
                    )

                item = yaml.safe_load(parameter.get("Value"))

                if item_type == "portfolios":
                    item["DisplayName"] = item_name
                    pipelines[file_name]["Portfolios"].append(item)
                elif item_type == "products":
                    item["Name"] = item_name
                    pipelines[file_name]["Products"].append(item)

        for file_name, items in pipelines.items():
            target_path = os.path.sep.join([target, "portfolios"])
            if not os.path.exists(target_path):
                os.makedirs(target_path)
            open(os.path.sep.join([target_path, f"{file_name}.yaml"]), "w").write(
                yaml.safe_dump(items)
            )
