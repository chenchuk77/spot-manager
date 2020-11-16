#!/usr/bin/python

import boto3
import json
import sys
import time
import socket
import os
import re
import subprocess
import traceback
from urllib2 import urlopen
from random import randint
from contextlib import closing

version = '1.30'
port_check_interval = 10

# aws sqs parameters
sqs = boto3.client('sqs',
                   aws_access_key_id     = os.environ['AWS_ACCESS_KEY_ID'],
                   aws_secret_access_key = os.environ['AWS_SECRET_ACCESS_KEY'],
                   region_name           = os.environ['AWS_DEFAULT_REGION'])

queue_url = os.environ['QUEUE_URL']

# commands and shortcuts
daemon  = ['--daemon',  '--d']
request = ['--request', '--r']

# list of all legal commands
commands = daemon + request

def show_usage():
    print ('pytunnel version {}'.format(version))
    print ('')
    print ('usage for server side:')
    print ('./EXAMPLE-pytunnel.py --daemon chen-dev39')
    print ('./EXAMPLE-pytunnel.py --d chen-dev39')
    print ('')
    print ('usage for client side:')
    print ('./EXAMPLE-pytunnel.py --request chen-dev39.json')
    print ('./EXAMPLE-pytunnel.py --r chen-dev39.json')

def read_properties(filename):
    if not os.path.isfile(filename):
        log('cannot open {}, file not found.'.format(filename))
        sys.exit(1)
    with open(filename) as json_data:
        data = json.load(json_data)
    return data

def log(msg):
    print ('{} - {}'.format(time.strftime("%x %H:%M:%S"), msg))

def random_seconds():
    # randomize to ensure that each server will poll on a different time
    return randint(0, 30) + 30

def delete_message():
    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)

def send_message(jsonobject):
    try:
        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(jsonobject)
        )
    except Exception:
        log(sys.exc_info()[0])

# client function
def check_port(port):
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        if sock.connect_ex(('127.0.0.1', port)) == 0:
            return True
        else:
            return False

def find_my_public_ip():
    my_ip_web_reply = urlopen('http://ifconfig.io').read()
    ip = re.findall( r'[0-9]+(?:\.[0-9]+){3}', my_ip_web_reply )
    if ip:
        log('requesting tunnel to ip:{} using http://ifconfig.io'.format(ip[0]))
        return ip[0]
    my_ip_web_reply = urlopen('http://ip.42.pl/raw').read()
    ip = re.findall( r'[0-9]+(?:\.[0-9]+){3}', my_ip_web_reply )
    if ip:
        log('requesting tunnel to ip:{} using http://ip.42.pl/raw '.format(ip[0]))
        return ip[0]
    log('cannot retrieve my own public ip. exiting client ...')
    sys.exit(1)

# server function to create tunnel on remote client
def create_ssh_reverse_tunnel(tunnel_properties):
    my_ssh_user   = tunnel_properties['my_ssh_user']
    my_ssh_ip     = tunnel_properties['my_ssh_ip']
    my_ssh_port   = tunnel_properties['my_ssh_port']
    my_app_port   = tunnel_properties['my_app_port']
    your_app_port = tunnel_properties['your_app_port']
    log('processing tunnel request: for {} at {}:{}'.format(my_ssh_user, my_ssh_ip, my_ssh_port))
    try:
        with open("./stdout.txt","wb") as out, open("./stderr.txt","wb") as err:
            # example command : ssh -N -R 0.0.0.0:2210:localhost:22 bhome.dyndns.com
            subprocess.Popen(['ssh', '-oStrictHostKeyChecking=no',
                              '-p', my_ssh_port,
                              '-N', '-R', '0.0.0.0:{}:localhost:{}'.format(my_app_port, your_app_port),
                              '{}@{}'.format(my_ssh_user, my_ssh_ip)])
    except:
        log('error creating ssh tunnel.')

# read args and decide if operating in request mode / daemon mode
# - request mode: fires a json request once to sqs queue and exit
# - daemon mode: listens forever for a new requests from sqs queue
#
tag = ''
mode = ''
if len(sys.argv) != 3:
    show_usage()
    sys.exit(1)
if sys.argv[1] not in commands:
    show_usage()
    sys.exit(1)
tag = sys.argv[2]
if not tag:
    show_usage()
    sys.exit(1)
if sys.argv[1] in daemon:
    mode = 'daemon'
elif sys.argv[1] in request:
    mode = 'request'
else:
    show_usage()
    sys.exit(1)



########################## request mode (client) ###########################
if mode == 'request':
    filename = './{}'.format(tag)
    if not 'json' in filename:
        filename += '.json'
    log('pytunnel client version {}'.format(version))
    log('sending tunnel request using {}.'.format(filename))

    data = read_properties(filename)
    # auto injecting the public ip if value is 'dynamic'
    if data['my_ssh_ip'] == 'dynamic':
        data['my_ssh_ip'] = find_my_public_ip()

    send_message(data)
    log('request sent for tunnel tag {}, check local port {}'.format(data['my_app_port'], data['tag']))

    while not check_port(int(data['my_app_port'])):
        log('waiting for local port {} to listen ...'.format(data['my_app_port']))
        time.sleep(port_check_interval)
    log('tunnel created for tag {}. you can now connect to localhost:{}'.format(data['tag'], data['my_app_port']))

########################## daemon mode (server) ###########################
if mode == 'daemon':
    log ('pytunnel server version {}, entering main loop.'.format(version))
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
        if response.has_key('Messages'):

            # parse
            message = response['Messages'][0]
            receipt_handle = message['ReceiptHandle']

            # decoding json
            try:
                # just check if its a json
                body = json.loads(message['Body'])
            # if not json content
            except ValueError:
                log('ignoring, non json content')
                log(body)

            body = json.loads(message['Body'])
            if body['tag'] == tag:
                log('handling new tunnel request for tag {}.'.format(tag))
                create_ssh_reverse_tunnel(body)
                log('tunnel created.')
                delete_message()
            else:
                log('unknown tag {}, cancelling and leaving the message on queue for other server.'.format(body['tag']))

        else:
            log('no messages in sqs')
        time.sleep(random_seconds())

