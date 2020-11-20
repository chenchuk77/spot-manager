#!/usr/bin/python3


import boto3

route53_client = boto3.client('route53')

hosted_zone_id='/hostedzone/ZSPS4JHX4X90T'
ns_record = 'lms-chen.lms.lumosglobal.com'
public_ip = '7.7.7.7'

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

x=5