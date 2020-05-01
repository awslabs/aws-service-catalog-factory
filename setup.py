# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="aws-service-catalog-factory",
    version="0.42.4",
    author="Eamonn Faherty",
    author_email="aws-service-catalog-tools@amazon.com",
    description="Making it easier to build out ServiceCatalog products",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/awslabs/aws-service-catalog-factory",
    packages=find_packages(),
    package_data={"servicecatalog_factory": ["*", "*/*", "*/*/*"]},
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Natural Language :: English",
    ],
    entry_points={
        "console_scripts": ["servicecatalog-factory = servicecatalog_factory.cli:cli"]
    },
    install_requires=[
        "astroid==2.4.0",
        "better-boto==0.26.0",
        "boto3==1.13.0",
        "botocore==1.16.0",
        "certifi==2020.4.5.1",
        "cfn-flip==1.2.1",
        "chardet==3.0.4",
        "click==7.0",
        "colorclass==2.2.0",
        "docopt==0.6.2",
        "docutils==0.14",
        "idna==2.8",
        "isort==4.3.21",
        "jinja2==2.10.1",
        "jmespath==0.9.5",
        "lazy-object-proxy==1.4.3",
        "lockfile==0.12.2",
        "luigi==2.8.6",
        "markupsafe==1.1.1",
        "mccabe==0.6.1",
        "pykwalify==1.7.0",
        "pylint==2.5.0",
        "python-daemon==2.1.2",
        "python-dateutil==2.8.1",
        "pyyaml==5.3.1",
        "requests==2.22.0",
        "s3transfer==0.3.3",
        "six==1.14.0",
        "terminaltables==3.1.0",
        "toml==0.10.0",
        "tornado==4.5.3",
        "typed-ast==1.4.1; implementation_name == 'cpython' and python_version < '3.8'",
        "urllib3==1.25.9; python_version != '3.4'",
        "wrapt==1.12.1",
    ],
)
