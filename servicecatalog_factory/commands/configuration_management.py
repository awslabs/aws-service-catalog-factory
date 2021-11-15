#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#  SPDX-License-Identifier: Apache-2.0
import json

import click
import yaml
from betterboto import client as betterboto_client

from servicecatalog_factory import constants


def upload_config(config):
    with betterboto_client.ClientContextManager("ssm") as ssm:
        ssm.put_parameter(
            Name=constants.CONFIG_PARAM_NAME,
            Type="String",
            Value=yaml.safe_dump(config),
            Overwrite=True,
        )
    click.echo("Uploaded config")


def set_regions(regions):
    with betterboto_client.ClientContextManager(
        "ssm", region_name=constants.HOME_REGION
    ) as ssm:
        try:
            response = ssm.get_parameter(Name=constants.CONFIG_PARAM_NAME)
            config = yaml.safe_load(response.get("Parameter").get("Value"))
        except ssm.exceptions.ParameterNotFound:
            config = {}
        config["regions"] = regions if len(regions) > 1 else regions[0].split(",")
        upload_config(config)


def add_secret(secret_name, oauth_token, secret_token):
    with betterboto_client.ClientContextManager("secretsmanager") as secretsmanager:
        try:
            secretsmanager.create_secret(
                Name=secret_name,
                SecretString=json.dumps(
                    {
                        "OAuthToken": oauth_token,
                        "SecretToken": secret_token or oauth_token,
                    }
                ),
            )
        except secretsmanager.exceptions.ResourceExistsException:
            secretsmanager.put_secret_value(
                SecretId=secret_name,
                SecretString=json.dumps(
                    {
                        "OAuthToken": oauth_token,
                        "SecretToken": secret_token or oauth_token,
                    }
                ),
                VersionStages=["AWSCURRENT",],
            )
    click.echo("Uploaded secret")
