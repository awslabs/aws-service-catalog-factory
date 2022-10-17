#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import json
import os


def should_pipelines_inherit_tags():
    should_pipelines_inherit_tags_value = os.environ.get(
        "SCT_SHOULD_PIPELINES_INHERIT_TAGS", None
    )
    if should_pipelines_inherit_tags_value is None:
        raise Exception("You must export SCT_SHOULD_PIPELINES_INHERIT_TAGS")
    return should_pipelines_inherit_tags_value.upper() == "TRUE"


def initialiser_stack_tags():
    initialiser_stack_tags_value = os.environ.get("SCT_INITIALISER_STACK_TAGS", None)
    if initialiser_stack_tags_value is None:
        raise Exception("You must export SCT_INITIALISER_STACK_TAGS")
    return json.loads(initialiser_stack_tags_value)
