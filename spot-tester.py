#!/usr/bin/python3

import boto3
import datetime
client = boto3.client('ec2')
response = client.request_spot_instances(
    DryRun=False,
    SpotPrice='0.05',
    ClientToken='string1',
    InstanceCount=1,
    Type='one-time',
    LaunchSpecification={
        'ImageId': 'ami-0fc8c8e37cd7db658',
        'InstanceType': 'm5a.large',
        'NetworkInterfaces': [
            {
                'AssociatePublicIpAddress': True,
                'DeviceIndex': 0,
                'Groups': ['sg-056964e89bbf05266'],
                'SubnetId': 'subnet-03fb65f37827a8971',
            },
        ]
    }
)
print('hello')

client = boto3.client('ec2')

request_new_spot('0.05', 'ami-0fc8c8e37cd7db658', 'm5a.large', 'sg-056964e89bbf05266', 'subnet-03fb65f37827a8971'):

def request_new_spot(spot_price, ami, type, sg, subnet):
    response = client.request_spot_instances(
        DryRun=False,
        SpotPrice=spot_price,
        ClientToken='string1',
        InstanceCount=1,
        Type='one-time',
        LaunchSpecification={
            'ImageId': ami,
            'InstanceType': type,
            'NetworkInterfaces': [
                {
                    'AssociatePublicIpAddress': True,
                    'DeviceIndex': 0,
                    'Groups': [sg],
                    'SubnetId': subnet,
                },
            ]
        }
    )
    return response


#
# This script should run when instance first launched (metadata)
# it will send a message to an SQS topic with the params (iid, private address, public address)
#
# remember to source env vars for aws access
# for testing, you can override the message by running locally with args:
#
# ./get-instance-metadata.py "this is a test message"
#

import boto3
from ec2_metadata import ec2_metadata
import json
import sys
import time
import os
#
# # aws sqs parameters
# sqs = boto3.client('sqs',
#                    aws_access_key_id     = os.environ['AWS_ACCESS_KEY_ID'],
#                    aws_secret_access_key = os.environ['AWS_SECRET_ACCESS_KEY'],
#                    region_name           = os.environ['AWS_DEFAULT_REGION'])
#
# queue_url = os.environ['QUEUE_URL']
# version='1.00'
#
# # default message can be overiden by arg1
# if len(sys.argv) > 1:
#     text = sys.argv[1]
# else:
#     text = "Lumos new spot instance launched"
#
# msg = {
#     "text": text,
#     "iid":        ec2_metadata.instance_id,
#     "public_ip":  ec2_metadata.public_ipv4,
#     "private_ip": ec2_metadata.private_ipv4
# }
#
# resp = sqs.send_message(
#     QueueUrl=queue_url,
#     MessageBody=json.dumps(msg))
#
# #print(resp['MessageId'])
# print ("Message has been sent to SQS.")