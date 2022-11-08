#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import json
import logging
import os
import traceback
from pathlib import Path

import luigi
from betterboto import client as betterboto_client

from servicecatalog_factory import constants

from servicecatalog_factory.waluigi import tasks as waluigi_tasks

logger = logging.getLogger(__file__)


class FactoryTask(waluigi_tasks.WaluigiTaskMixin, luigi.Task):
    def params_for_results_display(self):
        return {"task_reference": self.task_reference}

    @property
    def factory_account_id(self):
        account_id = os.environ.get("ACCOUNT_ID", None)
        if account_id is None:
            raise Exception("You must export ACCOUNT_ID")
        return account_id

    @property
    def should_pipelines_inherit_tags(self):
        should_pipelines_inherit_tags_value = os.environ.get(
            "SCT_SHOULD_PIPELINES_INHERIT_TAGS", None
        )
        if should_pipelines_inherit_tags_value is None:
            raise Exception("You must export SCT_SHOULD_PIPELINES_INHERIT_TAGS")
        return should_pipelines_inherit_tags_value.upper() == "TRUE"

    @property
    def initialiser_stack_tags(self):
        initialiser_stack_tags_value = os.environ.get(
            "SCT_INITIALISER_STACK_TAGS", None
        )
        if initialiser_stack_tags_value is None:
            raise Exception("You must export SCT_INITIALISER_STACK_TAGS")
        return json.loads(initialiser_stack_tags_value)

    @property
    def factory_region(self):
        region = os.environ.get("REGION", None)
        if region is None:
            raise Exception("You must export REGION")
        return region

    def client(self, service):
        return betterboto_client.ClientContextManager(service,)

    def regional_client(self, service):
        return betterboto_client.ClientContextManager(service, region_name=self.region,)

    def load_from_input(self, input_name):
        with self.input().get(input_name).open("r") as f:
            return json.loads(f.read())

    def info(self, message):
        logger.info(f"{self.uid}: {message}")

    def output(self):
        return luigi.LocalTarget(f"output/{self.uid}.json")

    def write_output(self, content):
        self.write_output_raw(json.dumps(content, indent=4, default=str,))

    def write_output_raw(self, content):
        with self.output().open("w") as f:
            f.write(content)

    @property
    def uid(self):
        return f"{self.__class__.__name__}/{self.task_reference}"


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
