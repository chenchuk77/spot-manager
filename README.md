# spot-manager
spot instance manager implemented in python3


The spot-manager manages the lifecycle of the spot instances. 
Its duty is to respond to SPOT_INTERRUPTION notifications, and request a new spot, hiding the complexity from the user. 

### Modules
1. spot-manager (listens infinitely to SQS queue and handle messages)
2. web-server (currently only notify the spot-manager for a new registration)
3. spot-image-creator (creates daily ami from spot and notify SQS *** NOT IMPLEMENTED YET ***)

*** NOTE: web-server is the only way to add a managed instance

### System components
![](spot-manager.png)

### Workflow example
1. user request to add instance lms-chen to web-server
1a. web server publishes SQS message for registration
1b. spot-manager poller receive the message and add lms-chen to a local db (its now managed)
2. spot-manager requests a new spot (sir) and updates the sir for lms-chen
3. sir is fulfilled by amazon
4. new spot launched the iid returned is updated for lms-chen
5. spot-manager updates its local db with new iid
6. the spot is running cloud-init code (once) for app reconfiguration (tomcat) with the new private ip address
7. the spot publish an SQS message with the new public_ip  and reboots
8. spot-manager receives the new spot message from SQS and changes the ns_record (route53) to refer to the new public ip address
8. user can now ping lms-chen.lms.lumosglobal.com
NOTE TESTED YET:
9. aws will notify SQS with "SPOT INTERRUPTION" 2 minutes before spot will go down
10. spot-manager will do again steps 4->8


### Assumptions
1. vm has self-deploy script
2. python 3.6 - 3.8 installed
3. cloud-init is working wo errors
4. vm has iam cred to send sqs msg
5. spot-image-creator 

*** NOTE

### Environment configuration
1. APIGW apache should use private NS to access core devices instead of private IPs
2. zookeeper config
server.1=mq1-stg39.lms.lumosglobal.com:2888:3888
server.2=mq2-stg39.lms.lumosglobal.com:2888:3888
server.3=mq3-stg39.lms.lumosglobal.com:2888:3888

2. Kafka connection string should use private NS:
zookeeper.connect=mq1-stg39.lms.lumosglobal.com:2181,mq2-stg39.lms.lumosglobal.com:2181,mq3-stg39.lms.lumosglobal.com:2181

3. configure backend (and other core service to use NS for kafka)
cp -ar conf/ conf.original
grep -R 2181
OLD_ZOO_CS=10.25.1.224:2181,10.25.1.125:2181,10.25.1.28:2181
NEW_ZOO_CS=mq1-stg39.lms.lumosglobal.com:2181,mq2-stg39.lms.lumosglobal.com:2181,mq3-stg39.lms.lumosglobal.com:2181
sed -i "s/${OLD_ZOO_CS}/${NEW_ZOO_CS}/g" backend-messaging.properties

grep -R 9092
OLD_KAFKA_CS=10.25.1.224:9092,10.25.1.125:9092,10.25.1.28:9092
NEW_KAFKA_CS=mq1-stg39.lms.lumosglobal.com:9092,mq2-stg39.lms.lumosglobal.com:9092,mq3-stg39.lms.lumosglobal.com:9092
sed -i "s/${OLD_KAFKA_CS}/${NEW_KAFKA_CS}/g" backend-messaging.properties



NOTE: kafka.rmi.server.hostname uses private ip but is meaningless, so no need to replace



TODO:
1. implement spot-image-creator
2. implement new-spot-image-created handler to updates the local record (next spot will use new image)


