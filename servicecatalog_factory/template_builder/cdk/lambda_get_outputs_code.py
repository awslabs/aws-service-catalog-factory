import json
from urllib.request import Request, urlopen
import boto3
import logging
from botocore.exceptions import ClientError
import time


def handler(event, context):
    request_type = event["RequestType"]
    try:
        if request_type in ["Create", "Update"]:
            properties = event.get("ResourceProperties")
            bucket_name = properties.get("BucketName")
            code_build_build_id = properties.get("CodeBuildBuildId")
            object_key_prefix = properties.get("ObjectKeyPrefix")
            object_key = f"{object_key_prefix}/scf_outputs-{code_build_build_id}.json"

            client = boto3.client("s3")
            print(bucket_name)
            print(object_key)

            response = None

            while response is None:
                try:
                    response = client.get_object(Bucket=bucket_name, Key=object_key,)
                except ClientError as ex:
                    if ex.response["Error"]["Code"] == "NoSuchKey":
                        print("Not yet found outputs file")
                        time.sleep(3)
                    else:
                        raise

            print("Found the outputs file")

            artifact = json.loads(response.get("Body").read())

            data = {"Message": f"{request_type} successful", **artifact}

            send_response(
                event, context, "SUCCESS", data,
            )

        else:
            send_response(
                event, context, "SUCCESS", {"Message": f"{request_type} successful",},
            )

    except Exception as ex:
        print(logging.traceback.format_exc())
        send_response(event, context, "FAILED", {"Message": f"Exception {ex}"})


def send_response(e, c, rs, rd):
    print("send_response", e, c, rs, rd)
    r = json.dumps(
        {
            "Status": rs,
            "Reason": "CloudWatch Log Stream: " + c.log_stream_name,
            "PhysicalResourceId": c.log_stream_name,
            "StackId": e["StackId"],
            "RequestId": e["RequestId"],
            "LogicalResourceId": e["LogicalResourceId"],
            "Data": rd,
        }
    )
    d = str.encode(r)
    h = {"content-type": "", "content-length": str(len(d))}
    req = Request(e["ResponseURL"], data=d, method="PUT", headers=h)
    r = urlopen(req)
