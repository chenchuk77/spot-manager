#!/usr/bin/python3

# from flask import Flask
# app = Flask(__name__)

import base64
import boto3
import json
import sys
import time
import socket
import os
import re
import subprocess
import traceback
from random import randint
from contextlib import closing
from db import Instance, Message, init
import logging

version='1.00'

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# ec2 client for spot requests
client = boto3.client('ec2')

# route 3 client
route53_client = boto3.client('route53')


# sqs client
sqs = boto3.client('sqs',
                   aws_access_key_id     = os.environ['AWS_ACCESS_KEY_ID'],
                   aws_secret_access_key = os.environ['AWS_SECRET_ACCESS_KEY'],
                   region_name           = os.environ['AWS_DEFAULT_REGION'])
queue_url = os.environ['QUEUE_URL']


def show_usage():
    print ('tester version {}'.format(version))
    print ('')


def log(msg):
    logger.info(msg)
    # print ('{} - {}'.format(time.strftime("%x %H:%M:%S"), msg))


# def request_new_spot():
#     print('TODO: request new spot')


def update_instance_state(iid):
    print('TODO: update instance state')


def random_seconds():
    # randomize to ensure that each server will poll on a different time
    return randint(0, 30) + 30


def delete_message(receipt_handle):
    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)


# EXAMPLE messages ( dict keys reduced for clarity )
# {'text': 'Lumos new spot instance launched', 'iid': 'i-123456789', 'public_ip': '3.3.3.3', 'private_ip': '10.6.6.6'}
# {'detail-type': 'EC2 Instance State-change Notification', 'detail': {'instance-id': 'i-03cfa8dd683e2d5bf', 'state': 'pending'}}
# {'detail-type': 'EC2 Spot Instance Interruption Warning', 'detail': {'instance-id': 'i-00b0d8c85295200b0', 'instance-action': 'terminate'}}
# {'detail-type': 'EC2 Spot Instance Request Fulfillment', 'detail': {'spot-instance-request-id': 'sir-mi5g76sm', 'instance-id': 'i-03cfa8dd683e2d5bf'}}

# update_instance_record(body['name'], body['price'], body['ami'], body['type'], body['sg'], body['subnet'])
#

def update_instance_record(name, sir, price, ami, _type, sg, subnet, public_access, ns_record):
    query = Instance.select().where(Instance.name == name)
    if query.exists():
        logger.info('updating record name: {}, with sir: {} params.'.format(name, sir))
        instance = Instance.select().where(Instance.name == name)[0]
        instance.sir = sir
        instance.price = price
        instance.ami = ami
        instance.type = _type
        instance.sg = sg
        instance.subnet = subnet
        instance.ns_record = ns_record
        instance.public_access = public_access
        instance.save()
    else:
        logger.info('adding new record: name: {} with sir: {} params.'.format(name, sir))
        instance = Instance.create(name=name, ns_record=ns_record, public_access=public_access, sir=sir, price=price, ami=ami, type=_type, sg=sg,
                                   subnet=subnet, state="spot-requested")
        instance.save()


def add_message_record(source, text, sent, body):
    logger.info('adding new record to Message table [from:{}, text:{}]'.format(source, text))
    message = Message.create(source=source, text=text, sent=sent, body=body)
    message.save()


#- {'text': 'New spot requested from web-server', 'price': '0.05', 'ami': 'ami-0fc8c8e37cd7db658', 'type': 'm5a.large', 'sg': 'sg-056964e89bbf05266', 'subnet': 'subnet-03fb65f37827a8971'}

def handle_incomming_message(body, receipt_handle, timestamp):

    # Must be False when running in prod. use True to clear
    # all messages in the SQS without handling ( 1 execution, then change back to False )
    #

    delete_all_queue_messages = False
    #delete_all_queue_messages = True

    if delete_all_queue_messages:
        delete_message(receipt_handle)
        return

    # Lumos message has a "text" field
    if 'text' in body.keys():
        log('got a Lumos message from topic.')
        if body['text'] == 'Lumos new spot instance launched':
            add_message_record(source="lumos", text=body['text'], sent=timestamp, body=body)
            logger.info('new spot instance launched: {}.'.format(body['iid']))
            query = Instance.select().where(Instance.iid == body['iid'])
            if query.exists():
                instance = Instance.select().where(Instance.iid == body['iid'])[0]
                instance.public_ip = body['public_ip']
                instance.private_ip = body['private_ip']
                logger.info('updating record for: {} with public_ip: {}, private_ip: {}.'
                            .format(instance.name, instance.public_ip, instance.private_ip))
                instance.save()
                if instance.ns_record == 'NONE':
                    logger.info('no DNS record for this spot, skipping route53')
                else:
                    logger.info('updating route53 for: {} [ns_record: {} public_ip: {}].'
                                .format(instance.name, instance.ns_record, instance.public_ip))
                    resp = change_ns_record(instance.name, instance.ns_record, instance.public_ip)
                logger.info('deleting message.')
                delete_message(receipt_handle)
            else:
                logger.info('ignoring new spot with iid: {} (not managed by spot-manager).'.format(body['iid']))

        elif body['text'] == 'New spot requested from web-server':
            logger.info('new spot request for {} : (price:{}, ami: {}, type: {}, sg: {}, subnet:{}, public_access: {})'
                        .format((body['name']), (body['price']), format(body['ami']), format(body['type']),format(body['sg']),format(body['subnet']), format(body['public_access'])))

            resp = request_new_spot(body['name'], body['price'], body['ami'], body['type'], body['sg'], body['subnet'], body['public_access'])
            # get the spot req id
            sir = resp['SpotInstanceRequests'][0]['SpotInstanceRequestId']
            update_instance_record(body['name'], sir, body['price'], body['ami'], body['type'], body['sg'],
                                   body['subnet'], body['public_access'], ns_record=body['ns_record'])
            logger.info('deleting message.')
            delete_message(receipt_handle)
        else:
            log('unknown error in lumos message')
            log(body)
        return

    # AWS message has a "detail-type" field
    if 'detail-type' in body.keys():
        log('got a AWS message from topic.')
        if body['detail-type'] == 'EC2 Instance State-change Notification':
            add_message_record(source=body['source'], text=body['detail-type'], sent=timestamp, body=body)
            log('instance {} change state to {}.'.format(body['detail']['instance-id'], body['detail']['state']))
            query = Instance.select().where(Instance.iid == body['detail']['instance-id'])
            if query.exists():
                logger.info('updating record iid: {}, with state: {} params.'
                            .format(body['detail']['instance-id'], body['detail']['state']))
                instance = Instance.select().where(Instance.iid == body['detail']['instance-id'])[0]
                instance.state = body['detail']['state']
                instance.save()
            else:
                logger.info('ignoring iid: {} (not managed by spot-manager).'.format(body['detail']['instance-id']))
            log('deleting message.')
            delete_message(receipt_handle)
            return
        elif body['detail-type'] == 'EC2 Spot Instance Interruption Warning':
            add_message_record(source=body['source'], text=body['detail-type'], sent=timestamp, body=body)
            log('spot {} is changing state to {}.'.format(body['detail']["instance-id"], body['detail']["instance-action"]))
            instance = Instance.select().where(Instance.iid == body['detail']["instance-id"])[0]
            instance.state = body['detail']["instance-action"]
            instance.save()
            log('instance record {} updated: iid: {}, state to {}.'.format(instance.name, body['detail']['instance-id'], body['detail']['instance-action']))
            log('deleting message.')
            delete_message(receipt_handle)
            return
        elif body['detail-type'] == 'EC2 Spot Instance Request Fulfillment':
            add_message_record(source=body['source'], text=body['detail-type'], sent=timestamp, body=body)
            log('spot request {} fulfilled. iid: {}.'.format(body['detail']['spot-instance-request-id'], body['detail']['instance-id']))
            instance = Instance.select().where(Instance.sir == body['detail']['spot-instance-request-id'])[0]
            instance.state = 'spot-fulfilled'
            instance.iid = body['detail']['instance-id']
            instance.save()
            log('instance: {} record updated: [iid: {} and state: spot-fulfilled.]'
                .format(instance.name, body['detail']['instance-id']))

            # instance = Instance.select().where(Instance.iid == body['detail']["instance-id"])[0]

            log('deleting message.')
            delete_message(receipt_handle)
            return
        else:
            log('unknown error in aws message')
            log(body)
        return


# request_new_spot('0.05', 'ami-0fc8c8e37cd7db658', 'm5a.large', 'sg-056964e89bbf05266', 'subnet-03fb65f37827a8971'):
def request_new_spot(name, spot_price, ami, _type, sg, subnet, public_access):
    public_access = str.lower(public_access) == 'true'

    sqs_config = """
# export into the environment
#

export AWS_ACCESS_KEY_ID=AKIAJFWBUQHTFIVVMSHA
export AWS_SECRET_ACCESS_KEY=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
export AWS_DEFAULT_REGION=eu-west-1
export QUEUE_URL=https://sqs.eu-west-1.amazonaws.com/390415077514/spot-test


"""

    publish_metadata_script = """#!/usr/bin/python3

#
# This script should run when instance first launched (metadata)
# it will send a message to an SQS topic with the params (iid, private address, public address)
#
# remember to source env vars for aws access
# for testing, you can override the message by running locally with args:
#
# ./publish-metadata.py 'this is a test message'
#

import boto3
from ec2_metadata import ec2_metadata
import json
import sys
import time
import os

# aws sqs parameters
sqs = boto3.client('sqs',
                   aws_access_key_id     = os.environ['AWS_ACCESS_KEY_ID'],
                   aws_secret_access_key = os.environ['AWS_SECRET_ACCESS_KEY'],
                   region_name           = os.environ['AWS_DEFAULT_REGION'])

queue_url = os.environ['QUEUE_URL']
version='1.10'

# default message can be overiden by arg1
if len(sys.argv) > 1:
    text = sys.argv[1]
else:
    text = 'Lumos new spot instance launched'
    
# change None value if no public ip exists
if ec2_metadata.public_ipv4 is None:
    public_ip = 'NONE'
else:
    public_ip = ec2_metadata.public_ipv4


msg = {
    'text': text,
    'iid':        ec2_metadata.instance_id,
    'public_ip':  public_ip,
    'private_ip': ec2_metadata.private_ipv4
}

resp = sqs.send_message(
    QueueUrl=queue_url,
    MessageBody=json.dumps(msg))

#print(resp['MessageId'])
print ('Message with own metadata has been sent to SQS.')
    """


    userdata_script = f"""#!/bin/bash

#
# DONT EXECUTE !
#
# This script will be executed only once on instance first launch
# do here:
#
# 1. local config changes
# 2. local services startup (may not be necessary)
# 3. change DNS A records using route53 (mat be done externally also), if local need aws credentials
# 4. change prompt (lms/root)

#LOG=/home/lms/user-data.output
LOG=/home/ubuntu/user-data.output
echo "$(date) - starting"                     >> $LOG
echo "executing userdata.sh"                  >> $LOG


echo "creating script to publish metadata"    >> $LOG
cat << EOF > /home/ubuntu/publish-metadata.py
{publish_metadata_script}
EOF
#echo "(publish_metadata_script)" > /home/ubuntu/publish-metadata.py
chmod +x /home/ubuntu/publish-metadata.py

echo "{sqs_config}"              > /home/ubuntu/sqs-config

echo "installing python3"                     >> $LOG
apt-get -yqq install python3-pip              >> $LOG
pip3 install -q boto3 ec2_metadata            >> $LOG
echo "python3 version: $(python3 -V)"         >> $LOG
echo "pip3 version: $(pip3 -V)"               >> $LOG

echo "sourcing credentials"                   >> $LOG
#source /home/lms/sqs-config
source /home/ubuntu/sqs-config
echo "publish metadata to SQS"                >> $LOG
#python3 /home/lms/publish-metadata.py        >> $LOG
python3 /home/ubuntu/publish-metadata.py      >> $LOG
#if [ -f "/home/lms/self-deploy.sh" ]; then
if [ -f "/home/lms/self-deploy.sh" ]; then
    echo "starting self redeployment"         >> $LOG
    #/home/lms/self-deploy.sh                 >> $LOG
    /home/ubuntu/self-deploy.sh               >> $LOG
    echo "waiting 20s before reboot"          >> $LOG
    sleep 20s
    reboot
else
    echo "skipping self redeployment script." >> $LOG
    echo "spot instance is ready."            >> $LOG
fi
echo "$(date) - done."                        >> $LOG

"""
    userdata_base64 = base64.b64encode(userdata_script.encode("ascii")).decode("ascii")

    log('requesting a new spot instance for {} [price: {}. ami: {}, type: {}]'
        .format(name, spot_price, ami, _type))

    response = client.request_spot_instances(
        DryRun=False,
        SpotPrice=spot_price,
        # ClientToken='string1',
        ClientToken='random-{}'.format(str(time.time())[0:10]),
        InstanceCount=1,
        Type='one-time',
        LaunchSpecification={
            'ImageId': ami,
            'InstanceType': _type,
            'UserData': userdata_base64,
            'NetworkInterfaces': [
                {
                    'AssociatePublicIpAddress': public_access,
                    #'AssociatePublicIpAddress': False,
                    #'AssociatePublicIpAddress': True,
                    'DeviceIndex': 0,
                    'Groups': [sg],
                    'SubnetId': subnet,
                },
            ]
        }
    )
    return response


def change_ns_record(name, ns_record, public_ip):

    hosted_zone_id = '/hostedzone/ZSPS4JHX4X90T'
    # ns_record = 'lms-chen.lms.lumosglobal.com'
    # public_ip = '7.7.7.7'

    response = route53_client.change_resource_record_sets(
        HostedZoneId=hosted_zone_id,
        ChangeBatch={
            'Comment': 'string',
            'Changes': [
                {
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': ns_record,
                        'Type': 'A',
                        'TTL': 123,
                        'ResourceRecords': [
                            {
                                'Value': public_ip
                            },
                        ]
                    }
                }
            ]
        }
    )
    return response


def main():
    if 'DB_INIT' in os.environ:
        if os.environ['DB_INIT'] == 'TRUE':
            init(recreate=True)
            logger.info("db initialized. ")
            sys.exit(0)
    else:
        init(recreate=False)
        logger.info("db started. ")
        start_poller()


def start_poller():
    log ('sqs tester version {}, entering main loop.'.format(version))
    while True:
        # get message
        response = sqs.receive_message(
            QueueUrl=queue_url,
            AttributeNames=['SentTimestamp'],
            MaxNumberOfMessages=1,
            MessageAttributeNames=['All'],
            VisibilityTimeout=0,
            WaitTimeSeconds=0
        )

        # if message exists
        if 'Messages' in response.keys():
            # parse
            message = response['Messages'][0]
            timestamp = message['Attributes']['SentTimestamp']
            receipt_handle = message['ReceiptHandle']

            # decoding json
            try:
                # just check if its a json
                body = json.loads(message['Body'])
                log(body)
                handle_incomming_message(body, receipt_handle, timestamp)

            # if not json content
            except ValueError:
                log('ignoring, non json content')
                log(body)
        else:
            log('no messages in sqs')
        time.sleep(1)


if __name__ == '__main__':
    main()

#
# @app.route('/')
# def hello():
#     return "Hello World!"
#
# if __name__ == '__main__':
#     app.run()
#     print('web server started .... app continue code execution here (poller )...')