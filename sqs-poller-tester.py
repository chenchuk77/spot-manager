#!/usr/bin/python3

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


# aws sqs parameters
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

def handle_incomming_message(body, receipt_handle):
    # Lumos message has a "text" field
    if 'text' in body.keys():
        log('got a Lumos message from topic.')
        if body['text'] == 'Lumos new spot instance launched' or body['text'] == '3333' or body[
            'text'] == 'hello test message':
            # log('new spot instance launched: {}.'.format(body['iid']))
            logger.info('new spot instance launched: {}.'.format(body['iid']))
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
            log('instance {} change state to {}.'.format(body['detail']["instance-id"], body['detail']["state"]))
            log('deleting message.')
            delete_message(receipt_handle)
            return
        elif body['detail-type'] == 'EC2 Spot Instance Interruption Warning':
            log('spot {} is changing state to {}.'.format(body['detail']["instance-id"], body['detail']["instance-action"]))
            log('deleting message.')
            delete_message()
            return
        elif body['detail-type'] == 'EC2 Spot Instance Request Fulfillment':
            log('spot request {} fulfilled. iid: {}.'.format(body['detail']["spot-instance-request-id"], body['detail']["instance-id"]))
            log('deleting message.')
            delete_message(receipt_handle)
            return
        else:
            log('unknown error in aws message')
            log(body)
        return


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
            receipt_handle = message['ReceiptHandle']

            # decoding json
            try:
                # just check if its a json
                body = json.loads(message['Body'])
                log(body)
                handle_incomming_message(body, receipt_handle)

            # if not json content
            except ValueError:
                log('ignoring, non json content')
                log(body)
        else:
            log('no messages in sqs')
        time.sleep(1)


if __name__ == '__main__':
    main()
