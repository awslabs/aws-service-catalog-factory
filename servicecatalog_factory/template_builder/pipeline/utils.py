#  Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0


def translate_category(category):
    return category.replace("products", "product")


def is_for_single_version(versions):
    return len(versions) == 1
