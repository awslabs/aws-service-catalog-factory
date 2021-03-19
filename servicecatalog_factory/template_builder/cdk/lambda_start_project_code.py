import json
from urllib.request import Request, urlopen
import boto3
import logging


def handler(event, context):
    request_type = event["RequestType"]
    try:
        if request_type in ["Create", "Update"]:
            properties = event.get("ResourceProperties")
            project_name = properties.get("Project")
            codebuild = boto3.client("codebuild")
            args = [
                "CDK_DEPLOY_EXTRA_ARGS",
                "CDK_TOOLKIT_STACK_NAME",
                "PUPPET_ACCOUNT_ID",
                "CDK_DEPLOY_PARAMETER_ARGS",
                "CDK_DEPLOY_REQUIRE_APPROVAL",
                "NAME",
                "VERSION",
            ]

            evo = [
                {
                    "name": "ON_COMPLETE_URL",
                    "value": properties.get("Handle"),
                    "type": "PLAINTEXT",
                },
            ] + [
                {"name": p, "type": "PLAINTEXT", "value": properties.get(p)}
                for p in args
            ]

            print(evo)

            bootstrapper_build = codebuild.start_build(
                projectName=project_name, environmentVariablesOverride=evo,
            ).get("build")
            build_status = bootstrapper_build.get("buildStatus")
            build_id = bootstrapper_build.get("id")
            send_response(
                event,
                context,
                "SUCCESS",
                {
                    "Message": f"{request_type} successful.  Build status: {build_status}",
                    "BuildId": build_id,
                },
            )
        else:
            send_response(
                event, context, "SUCCESS", {"Message": f"{request_type} successful",},
            )

    except Exception as ex:
        print(logging.traceback.format_exc())
        send_response(event, context, "FAILED", {"Message": f"Exception {ex}"})


def send_response(e, c, status, data):
    print(e, c, status, data)
    r = json.dumps(
        {
            "Status": status,
            "Reason": "CloudWatch Log Stream: " + c.log_stream_name,
            "PhysicalResourceId": c.log_stream_name,
            "StackId": e["StackId"],
            "RequestId": e["RequestId"],
            "LogicalResourceId": e["LogicalResourceId"],
            "Data": data,
        }
    )
    d = str.encode(r)
    h = {"content-type": "", "content-length": str(len(d))}
    req = Request(e["ResponseURL"], data=d, method="PUT", headers=h)
    r = urlopen(req)
