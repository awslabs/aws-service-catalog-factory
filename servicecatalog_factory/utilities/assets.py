#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os


def resolve_from_site_packages(what):
    return os.path.sep.join(
        [os.path.dirname(os.path.abspath(os.path.sep.join([__file__, ".."]))), what]
    )


def read_from_site_packages(what):
    return open(resolve_from_site_packages(what), "r").read()
