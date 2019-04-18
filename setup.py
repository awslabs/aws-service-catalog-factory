# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="aws-service-catalog-factory",
    version="0.1.23",
    author="Eamonn Faherty",
    author_email="aws-service-catalog-tools@amazon.com",
    description="Making it easier to build out ServiceCatalog products",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/awslabs/aws-service-catalog-factory",
    packages=setuptools.find_packages(),
    package_data={'servicecatalog_factory': ['*','*/*','*/*/*']},
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Natural Language :: English",
    ],
    entry_points={
        'console_scripts': [
            'servicecatalog-factory = servicecatalog_factory.cli:cli'
        ]},
    install_requires=[
        'pyyaml',
        'click',
        'Jinja2',
        'boto3',
        'pykwalify',
        'better-boto>=0.6.8',
    ],
)
