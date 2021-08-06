#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import os
import shutil

from servicecatalog_factory.utilities.assets import resolve_from_site_packages


def seed(complexity, p):
    target = os.path.sep.join([p, "portfolios"])
    if not os.path.exists(target):
        os.makedirs(target)

    example = "example-{}.yaml".format(complexity)
    shutil.copy2(
        resolve_from_site_packages(os.path.sep.join(["portfolios", example])),
        os.path.sep.join([target, example]),
    )
