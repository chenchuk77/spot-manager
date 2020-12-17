
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
    public_access = request.args.get('public_access')
    price = request.args.get('price')
    ami = request.args.get('ami')
    _type = request.args.get('type')
    sg = request.args.get('sg')
    subnet = request.args.get('subnet')
    print("flask requested to request spot: ", price, ami, type, sg, subnet)
    msg = {
        "text": "New spot requested from web-server",
        "name": name,
        "ns_record": ns_record,
        "public_access": public_access,
        "price": price,
        "ami": ami,
        "type": _type,
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
    print('http://localhost:5000/add?name=lms-chen&ns_record=lms-chen.lms.lumosglobal.com&public_access=TRUE&price=0.05&ami=ami-04a9e867a6b73f809&type=m5a.large&sg=sg-056964e89bbf05266&subnet=subnet-03fb65f37827a8971')

    print('stg39 examples (active):')
    print('http://localhost:5000/add?name=stg39-worker-AIRTEL_NG&ns_record=NONE&public_access=FALSE&price=0.07&ami=ami-0844145828210fb97&type=m5a.large&sg=sg-04d70b57e6f937416&subnet=subnet-06777d83e0e56e0c0')
    print('http://localhost:5000/add?name=stg39-smsbroker-AIRTEL_NG&ns_record=NONE&public_access=FALSE&price=0.01&ami=ami-00c94fc9dff81a519&type=t3.micro&sg=sg-015cd9b5c3a77a9ee&subnet=subnet-04e5608c7de85605d')

    print('core services cant be spotted (VPN use private ips, apigw use private ips (DONT INVOKE THOSE SAMPLES):')
    print('http://localhost:5000/add?name=stg39-backend&ns_record=NONE&public_access=FALSE&price=0.02&ami=ami-0d752435eab8293c2&type=t3.medium&sg=sg-03f3287e9081317c0&subnet=subnet-0dba940b83e9b00df')
    print('http://localhost:5000/add?name=stg39-identity&ns_record=NONE&public_access=FALSE&price=0.015&ami=ami-08538b40bb11b6567&type=t3.small&sg=sg-0b62161dbdf4d3c95&subnet=subnet-06ee25ea692ea44b8')
    print('http://localhost:5000/add?name=stg39-rating&ns_record=NONE&public_access=FALSE&price=0.02&ami=ami-0bf055dbd6cb376b1&type=t3.medium&sg=sg-0d212b1bc797e3254&subnet=subnet-0e397066b3b5e6d50')

    print('check db instances table:')
    print('http://localhost:5000/instances')
    print('check db message table:')
    print('http://localhost:5000/messages')

    app.run()
