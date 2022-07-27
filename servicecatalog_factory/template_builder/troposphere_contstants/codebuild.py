#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0

from troposphere import codepipeline

ACTION_TYPE_ID_FOR_BUILD = codepipeline.ActionTypeId(
    Category="Build", Owner="AWS", Version="1", Provider="CodeBuild",
)
ACTION_TYPE_ID_FOR_TEST = codepipeline.ActionTypeId(
    Category="Test", Owner="AWS", Version="1", Provider="CodeBuild",
)
ACTION_TYPE_ID_FOR_PACKAGE = ACTION_TYPE_ID_FOR_BUILD
ACTION_TYPE_ID_FOR_DEPLOY = ACTION_TYPE_ID_FOR_BUILD
