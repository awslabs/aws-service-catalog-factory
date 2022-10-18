#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import json
import orjson

import yaml


class Equals(yaml.YAMLObject):
    yaml_loader = yaml.SafeLoader
    yaml_dumper = yaml.SafeDumper

    yaml_tag = u"!Equals"

    def __init__(self, values):
        self.values = values

    @classmethod
    def from_yaml(cls, constructor, node):
        x = constructor.construct_sequence(node)
        return cls(values=x)

    @classmethod
    def to_yaml(cls, dumper, data):
        return dumper.represent_sequence(cls.yaml_tag, data.values)

    def get_result(self):
        return all(element == self.values[0] for element in self.values)


class Not(yaml.YAMLObject):
    yaml_loader = yaml.SafeLoader
    yaml_dumper = yaml.SafeDumper

    yaml_tag = u"!Not"

    def __init__(self, values):
        self.values = values

    @classmethod
    def from_yaml(cls, constructor, node):
        x = constructor.construct_sequence(node)
        return cls(values=x)

    @classmethod
    def to_yaml(cls, dumper, data):
        return dumper.represent_sequence(cls.yaml_tag, data.values)

    def get_result(self):
        return not self.values[0]


def load(what):
    return yaml.safe_load(what)


def dump(what):
    return yaml.safe_dump(what, default_flow_style=False, width=1000000)


def dump_as_json(input):
    return json.dumps(input, default=str)


def load_as_json(input):
    return json_loads(input)


def json_dumps(obj):
    return orjson.dumps(obj, option=orjson.OPT_INDENT_2)


def json_loads(s):
    return orjson.loads(s)
