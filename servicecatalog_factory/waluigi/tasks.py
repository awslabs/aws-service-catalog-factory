#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import functools
import json
import os
import logging
import luigi
import traceback
from datetime import datetime
from pathlib import Path

from servicecatalog_factory import constants
from servicecatalog_factory.common import serialisation_utils, utils
from servicecatalog_factory.workflow.dependencies import task_factory

logger = logging.getLogger(constants.FACTORY_LOGGER_NAME)


def record_event(event_type, task, extra_event_data=None):
    task_type = task.__class__.__name__
    task_params = task.param_kwargs
    pid = os.getpid()
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    event = {
        "event_type": event_type,
        "task_type": task_type,
        "task_params": task_params,
        "params_for_results": task.params_for_results_display(),
        "datetime": current_datetime,
        "pid": os.getpid(),
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


class WaluigiTaskMixin:
    task_reference = luigi.Parameter()
    dependencies_by_reference = luigi.ListParameter()
    manifest_files_path = luigi.Parameter()

    def requires(self):
        return dict(reference_dependencies=self.dependencies_for_task_reference())

    @functools.lru_cache(maxsize=32)
    def get_task_from_reference(self, task_reference):
        f = open(
            f"{self.manifest_files_path}/tasks/{utils.escape(task_reference)}.json", "r"
        )
        c = f.read()
        f.close()
        return serialisation_utils.load_as_json(c)

    @functools.lru_cache(maxsize=32)
    def dependencies_for_task_reference(self):
        dependencies = dict()

        this_task = self.get_task_from_reference(self.task_reference)
        if this_task is None:
            raise Exception(f"Did not find {self.task_reference} within reference")
        for dependency_by_reference in this_task.get("dependencies_by_reference", []):
            dependency_by_reference_params = self.get_task_from_reference(
                dependency_by_reference
            )
            if dependency_by_reference_params is None:
                raise Exception(
                    f"{self.task_reference} has a dependency: {dependency_by_reference} unsatisfied by the manifest task reference"
                )
            t_reference = dependency_by_reference_params.get("task_reference")
            dependencies[t_reference] = task_factory.create(
                self.manifest_files_path,
                "",
                # self.manifest_task_reference_file_path,
                dependency_by_reference_params,
            )
        return dependencies

    def get_output_from_reference_dependency(self, reference):
        f = self.input().get("reference_dependencies").get(reference).open("r")
        content = f.read()
        f.close()
        return serialisation_utils.json_loads(content)

    def get_output_from_reference_dependency_raw(self, reference):
        f = self.input().get("reference_dependencies").get(reference).open("r")
        content = f.read()
        f.close()
        return content

    @property
    def should_use_caching(self):
        return False

    def execute(self):
        if self.should_use_caching:
            if self.complete():
                for task_reference, output in (
                    self.input().get("reference_dependencies", {}).items()
                ):
                    s3_url = output.path.split("/")
                    bucket = s3_url[2]
                    key = "/".join(s3_url[3:])
                    if key.endswith("latest.json"):
                        target = key
                    else:
                        target = ".".join(key.split(".")[0:-1])
                    target_dir = target.replace("/latest.json", "")
                    if not os.path.exists(target_dir):
                        os.makedirs(target_dir)
                    if not os.path.exists(target):
                        with self.hub_client("s3") as s3:
                            s3.download_file(Bucket=bucket, Key=key, Filename=target)
            else:
                self.run()
                self.execute()
        else:
            if not self.complete():
                self.run()

    def get_processing_time_details(self):
        task_details = dict(**self.param_kwargs)
        task_details.update(self.params_for_results_display())
        return self.__class__.__name__, task_details

    def on_task_failure(self, exception, duration):
        exception_details = {
            "exception_type": type(exception),
            "exception_stack_trace": traceback.format_exception(
                etype=type(exception), value=exception, tb=exception.__traceback__,
            ),
            "duration": duration,
        }
        record_event("failure", self, exception_details)

    def on_task_start(self):
        task_name = self.__class__.__name__
        logger.info(f"{task_name}:{self.task_reference} started")
        record_event("start", self)

    def on_task_success(self, duration):
        record_event("success", self, dict(duration=duration))

    def on_task_timeout(self):
        record_event("timeout", self)

    def on_task_process_failure(self, error_msg):
        exception_details = {
            "exception_type": "PROCESS_FAILURE",
            "exception_stack_trace": error_msg,
        }
        record_event("process_failure", self, exception_details)

    def on_task_broken_task(self, exception):
        record_event("broken_task", self, {"exception": exception})
