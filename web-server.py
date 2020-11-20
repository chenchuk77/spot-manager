
from flask import Flask
from flask import request
from datetime import datetime
import boto3
import json
import os
from db import Instance, Message, init
import pandas as pd

# db access
init()

# aws sqs parameters
sqs = boto3.client('sqs',
                   aws_access_key_id     = os.environ['AWS_ACCESS_KEY_ID'],
                   aws_secret_access_key = os.environ['AWS_SECRET_ACCESS_KEY'],
                   region_name           = os.environ['AWS_DEFAULT_REGION'])

queue_url = os.environ['QUEUE_URL']
version='1.00'

start_time = datetime.now()
app = Flask(__name__)


@app.route('/')
def test():
    return "flask is running for {} seconds...".format(datetime.now() - start_time)


@app.route('/add', methods=['GET'])
def add_managed_instance():
    name = request.args.get('name')
    ns_record = request.args.get('ns_record')
    price = request.args.get('price')
    ami = request.args.get('ami')
    type = request.args.get('type')
    sg = request.args.get('sg')
    subnet = request.args.get('subnet')
    print("flask requested to request spot: ", price, ami, type, sg, subnet)
    msg = {
        "text": "New spot requested from web-server",
        "name": name,
        "ns_record": ns_record,
        "price": price,
        "ami": ami,
        "type": type,
        "sg": sg,
        "subnet": subnet
    }
    resp = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(msg))
    return "Message {} has been sent to SQS.", resp['MessageId']


@app.route('/instances', methods=['GET'])
def show_db_instance_table():
    # creating HTML table from list
    instances = []
    query = Instance.select().dicts()
    for row in query:
        instances.append(row)
    df = pd.DataFrame(data=instances)
    df = df.fillna(' ').T
    resp = df.to_html()
    return resp


@app.route('/messages', methods=['GET'])
def show_db_message_table():
    # creating HTML table from dict
    messages = {}
    query = Message.select().dicts()
    msg_id = 0
    for row in query:
        messages[msg_id] = row
        msg_id += 1
    df = pd.DataFrame(data=messages)
    df = df.fillna(' ').T
    resp = df.to_html()
    return resp


if __name__ == '__main__':
    print('web server started - listening to spot requests')
    print('add spot request example:')
    print('http://localhost:5000/add?name=lms-chen&ns_record=lms-chen.lms.lumosglobal.com&price=0.05&ami=ami-04a9e867a6b73f809&type=m5a.large&sg=sg-056964e89bbf05266&subnet=subnet-03fb65f37827a8971')
    print('check db instances table:')
    print('http://localhost:5000/instances')
    print('check db message table:')
    print('http://localhost:5000/messages')

    app.run()
