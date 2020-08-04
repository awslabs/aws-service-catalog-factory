from betterboto import client as betterboto_client
from . import constants


def get_stack_version():
    with betterboto_client.ClientContextManager(
        "ssm", region_name=constants.HOME_REGION
    ) as ssm:
        return (
            ssm.get_parameter(Name="service-catalog-factory-version")
            .get("Parameter")
            .get("Value")
        )
