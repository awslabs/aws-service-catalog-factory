#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from unittest import mock as mocker


@mocker.patch("servicecatalog_factory.commands.bootstrap.bootstrap")
def test_bootstrap_branch(bootstrap_mocked):
    # setup
    from servicecatalog_factory.commands import bootstrap

    branch_name = "foo"
    (
        branch_to_bootstrap,
        source_provider,
        owner,
        repo,
        branch,
        poll_for_source_changes,
        webhook_secret,
        scm_connection_arn,
        scm_full_repository_id,
        scm_branch_name,
        scm_bucket_name,
        scm_object_key,
        create_repo,
    ) = (
        branch_name,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )
    # exercise
    bootstrap.bootstrap_branch(
        branch_to_bootstrap,
        source_provider,
        owner,
        repo,
        branch,
        poll_for_source_changes,
        webhook_secret,
        scm_connection_arn,
        scm_full_repository_id,
        scm_branch_name,
        scm_bucket_name,
        scm_object_key,
        create_repo,
    )

    # verify
    assert (
        bootstrap.constants.VERSION
        == "https://github.com/awslabs/aws-service-catalog-factory/archive/{}.zip".format(
            branch_name
        )
    )
    bootstrap_mocked.assert_called_once()
