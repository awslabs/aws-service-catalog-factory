# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import json, logging, time
from urllib.request import Request, urlopen
from betterboto import client as betterboto_client
import os
import traceback


logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.basicConfig(
    format='%(levelname)s %(threadName)s [%(filename)s:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d:%H:%M:%S',
    level=logging.INFO
)


def handler(event, context):
    request_type = event['RequestType']
    try:
        logger.info(request_type)
        if request_type == 'Create':
            target_account_id = event.get('ResourceProperties').get('TargetAccountId')
            puppet_account_id = event.get('ResourceProperties').get('PuppetAccountId')
            organization_account_access_role_name = event.get('ResourceProperties').get(
                'OrganizationAccountAccessRoleName')

            organization_account_access_role_arn = 'arn:aws:iam::{}:role/{}'.format(
                target_account_id, organization_account_access_role_name
            )

            bootstrapper_project_name = os.environ.get('BOOTSTRAPPER_PROJECT_NAME')

            with betterboto_client.ClientContextManager(
                    'codebuild',
            ) as codebuild:
                build = codebuild.start_build(
                    projectName=bootstrapper_project_name,
                    environmentVariablesOverride=[
                        {
                            'name': 'PUPPET_ACCOUNT_ID',
                            'value': puppet_account_id,
                            'type': 'PLAINTEXT'
                        },
                        {
                            'name': 'ORGANIZATION_ACCOUNT_ACCESS_ROLE_ARN',
                            'value': organization_account_access_role_arn,
                            'type': 'PLAINTEXT'
                        },
                    ],
                ).get('build')
                build_id = build.get('id')

                while build.get('buildStatus') == 'IN_PROGRESS':
                    response = codebuild.batch_get_builds(ids=[build_id])
                    build = response.get('builds')[0]
                    time.sleep(5)
                    logger.info("current status: {}".format(build.get('buildStatus')))

                final_status = build.get('buildStatus')

                if final_status == 'SUCCEEDED':
                    send_response(
                        event,
                        context,
                        "SUCCESS",
                        {
                            "Message": "Resource creation successful!",
                            "build_id": build_id,
                        }
                    )
                else:
                    logger.error('Errored check the logs: {}'.format(build.get('logs').get('deepLink')))
                    send_response(
                        event,
                        context,
                        "FAILED",
                        {
                            "Message": 'Errored check the logs: {}'.format(build.get('logs').get('deepLink')),

                        }
                    )

        elif request_type == 'Update':
            send_response(event, context, "SUCCESS",
                          {"Message": "Updated"})
        elif request_type == 'Delete':
            send_response(event, context, "SUCCESS",
                          {"Message": "Deleted"})
        else:
            send_response(event, context, "FAILED",
                          {"Message": "Unexpected"})
    except Exception as ex:
        logger.error(ex)
        traceback.print_tb(ex.__traceback__)
        send_response(
            event,
            context,
            "FAILED",
            {
                "Message": "Exception"
            }
        )


def send_response(e, c, rs, rd):
    r = json.dumps({
        "Status": rs,
        "Reason": "CloudWatch Log Stream: " + c.log_stream_name,
        "PhysicalResourceId": c.log_stream_name,
        "StackId": e['StackId'],
        "RequestId": e['RequestId'],
        "LogicalResourceId": e['LogicalResourceId'],
        "Data": rd
    })
    d = str.encode(r)
    h = {
        'content-type': '',
        'content-length': str(len(d))
    }
    req = Request(e['ResponseURL'], data=d, method='PUT', headers=h)
    r = urlopen(req)
    logger.info("Status message: {} {}".format(r.msg, r.getcode()))
