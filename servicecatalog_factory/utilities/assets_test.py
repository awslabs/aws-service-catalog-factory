#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
from unittest import mock as mocker


@mocker.patch("os.path.abspath", return_value="some/path/asset.py")
def test_resolve_from_site_packages(abspath_mocked):
    # setup
    from servicecatalog_factory.utilities import assets as sut

    what = "asset.py"
    site_path = os.path.sep.join(["some", "path"])
    expected_result = os.path.sep.join([site_path, what])

    # execute
    actual_result = sut.resolve_from_site_packages(what)

    # verify
    assert expected_result == actual_result


@mocker.patch("builtins.open")
def test_read_from_site_packages(mocked_open):
    # setup
    from servicecatalog_factory.utilities import assets as sut

    what = "asset.py"
    expected_result = "foobar"
    mocked_open().read.return_value = expected_result
    mocker.patch.object(sut, "resolve_from_site_packages", return_value="ignored")

    # execute
    actual_result = sut.read_from_site_packages(what)

    # verify
    assert expected_result == actual_result
