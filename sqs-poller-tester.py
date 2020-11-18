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


def request_new_spot():
    print('TODO: request new spot')


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

def update_instance_record(name, sir, price, ami, _type, sg, subnet, ns_record=""):
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
        instance.save()
    else:
        logger.info('adding new record: name: {} with sir: {} params.'.format(name, sir))
        instance = Instance.create(name=name, ns_record=ns_record, sir=sir, price=price, ami=ami, type=_type, sg=sg,
                                   subnet=subnet, state="spot-requested")
        instance.save()


def add_message_record(source, text, sent, body):
    logger.info('adding new record to Message table [from:{}, text{}]'.format(source, text))
    message = Message.create(source=source, text=text, sent=sent, body=body)
    message.save()


#- {'text': 'New spot requested from spot-manager', 'price': '0.05', 'ami': 'ami-0fc8c8e37cd7db658', 'type': 'm5a.large', 'sg': 'sg-056964e89bbf05266', 'subnet': 'subnet-03fb65f37827a8971'}

def handle_incomming_message(body, receipt_handle, timestamp):

    # Must be False when running in prod. use True to clear
    # all messages in the SQS without handling ( 1 execution, then change back to False )
    #
    # delete_all_queue_messages = True
    delete_all_queue_messages = False

    if delete_all_queue_messages:
        delete_message(receipt_handle)
        return

    # Lumos message has a "text" field
    if 'text' in body.keys():
        log('got a Lumos message from topic.')
        if body['text'] == 'Lumos new spot instance launched':
            logger.info('new spot instance launched: {}.'.format(body['iid']))
            add_message_record(source="lumos", text=body['text'], sent=timestamp, body=body)
            logger.info('deleting message.')
            delete_message(receipt_handle)

        elif body['text'] == 'New spot requested from spot-manager':
            logger.info('new spot request for {} : (price:{}, ami: {}, type: {}, sg: {}, subnet:{})'
                        .format((body['name']), (body['price']), format(body['ami']), format(body['type']),format(body['sg']),format(body['subnet'])))
            resp = request_new_spot(body['price'], body['ami'], body['type'], body['sg'], body['subnet'])
            # get the spot req id
            sir = resp['SpotInstanceRequests'][0]['SpotInstanceRequestId']
            update_instance_record(body['name'], sir, body['price'], body['ami'], body['type'], body['sg'], body['subnet'])
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
def request_new_spot(spot_price, ami, type, sg, subnet):
    userdata_script = """#!/bin/bash
      # DONT EXECUTE !
      #
      # This script will be executed only once on instance first launch
      # do here:
      #
      # 1. local config changes
      # 2. local services startup (may not be necessary)
      # 3. change DNS A records using route53 (mat be done externally also), if local need aws credentials
      # 4. change prompt (lms/root)
      #
      LOG=/home/lms/user-data.output
      echo "$(date) - starting"         >> ${LOG}
      echo "executing userdata.sh"      >> ${LOG}
      echo "sourcing credentials"       >> ${LOG}
      source /home/lms/sqs-config
      python3 publish-metadata.py
      echo "$(date) - done."            >> ${LOG}
      reboot
    """

    # self.output_template = base64.b64encode(output_template.encode("ascii")).decode("ascii")

    response = client.request_spot_instances(
        DryRun=False,
        SpotPrice=spot_price,
        # ClientToken='string1',
        ClientToken='random-{}'.format(str(time.time())[0:10]),
        InstanceCount=1,
        Type='one-time',
        LaunchSpecification={
            'ImageId': ami,
            'InstanceType': type,
            'UserData': userdata_script,
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
    x=1
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