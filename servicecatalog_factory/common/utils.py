#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0


def escape(input):
    return input.replace("-", "_").replace("/", "__")


def unwrap(what):
    if hasattr(what, "get_wrapped"):
        return unwrap(what.get_wrapped())

    if isinstance(what, dict):
        thing = dict()
        for k, v in what.items():
            thing[k] = unwrap(v)
        return thing

    if isinstance(what, tuple):
        thing = list()
        for v in what:
            thing.append(unwrap(v))
        return thing

    if isinstance(what, list):
        thing = list()
        for v in what:
            thing.append(unwrap(v))
        return thing

    return what
