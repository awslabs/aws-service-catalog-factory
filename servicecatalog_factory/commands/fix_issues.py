#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
from servicecatalog_factory.commands.portfolios import fix_issues_for_portfolio


def fix_issues(p):
    fix_issues_for_portfolio(p)
