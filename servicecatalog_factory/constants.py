# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os

import pkg_resources

OUTPUT = "output"
HASH_PREFIX = 'a'
CONFIG_PARAM_NAME = "/servicecatalog-factory/config"
PUBLISHED_VERSION = pkg_resources.require("aws-service-catalog-factory")[0].version
VERSION = PUBLISHED_VERSION
BOOTSTRAP_STACK_NAME = 'servicecatalog-factory'
SERVICE_CATALOG_FACTORY_REPO_NAME = 'ServiceCatalogFactory'
NON_RECOVERABLE_STATES = [
    "ROLLBACK_COMPLETE",
    'CREATE_IN_PROGRESS',
    'ROLLBACK_IN_PROGRESS',
    'DELETE_IN_PROGRESS',
    'UPDATE_IN_PROGRESS',
    'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS',
    'UPDATE_ROLLBACK_IN_PROGRESS',
    'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS',
    'REVIEW_IN_PROGRESS',
]
PRODUCT = 'product.j2'
COMPONENT = 'component.j2'
COMPONENT_GROUP = 'component_group.j2'
ASSOCIATIONS = 'associations.j2'
HOME_REGION = os.environ.get('AWS_DEFAULT_REGION', 'eu-west-1')


RESULTS_DIRECTORY = "results"