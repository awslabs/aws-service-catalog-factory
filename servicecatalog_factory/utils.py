#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import collections
import os

import jinja2
from copy import deepcopy


def resolve_from_site_packages(what):
    return os.path.sep.join([os.path.dirname(os.path.abspath(__file__)), what])


def read_from_site_packages(what):
    return open(resolve_from_site_packages(what), "r").read()


TEMPLATE_DIR = resolve_from_site_packages("templates")

ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATE_DIR), extensions=["jinja2.ext.do"],
)


def merge(dict1, dict2):
    if hasattr(dict1, "get_wrapped"):
        result = deepcopy(dict1.get_wrapped())
    else:
        result = deepcopy(dict1)
    for key, value in dict2.items():
        if isinstance(value, collections.Mapping):
            result[key] = merge(result.get(key, {}), value)
        else:
            result[key] = deepcopy(dict2[key])
    return result


def unwrap(input):
    if hasattr(input, "get_wrapped"):
        result = input.get_wrapped()
    else:
        result = input

    if isinstance(result, dict):
        for k in result.keys():
            result[k] = unwrap(result.get(k))

    return result
