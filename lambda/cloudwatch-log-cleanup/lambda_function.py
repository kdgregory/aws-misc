#
# Lambda function to delete CloudWatch log streams that have exceeded
# their group's retention period.
#

import boto3
import json
import time

client = boto3.client('logs')
    
def lambda_handler(event, context):
    paginator = client.get_paginator('describe_log_groups')
    itx = paginator.paginate()
    for page in itx:
        for group in page['logGroups']:
            processLogGroup(group['logGroupName'], group.get('retentionInDays'))
            
def processLogGroup(groupName, retentionInDays):
    print(f"examining {groupName}, retention period = {retentionInDays}")
    
    if (retentionInDays == None):
        return
    
    paginator = client.get_paginator('describe_log_streams')
    itx = paginator.paginate(logGroupName=groupName)
    for page in itx:
        for stream in page['logStreams']:
            processLogStream(groupName, retentionInDays, stream['logStreamName'], stream['creationTime'], stream.get('lastEventTimestamp'))
            
def processLogStream(groupName, retentionInDays, streamName, creationTime, latestTimestamp):
    lastActivity = creationTime
    if (latestTimestamp != None):
        lastActivity = max(lastActivity, latestTimestamp)
        
    deleteLimit = (int(time.time()) - (86400 * (retentionInDays + 1))) * 1000
    if (lastActivity < deleteLimit):
        lastActivityStr = time.asctime(time.gmtime(lastActivity / 1000))
        print(f"deleting {groupName} / {streamName}: last activity {lastActivityStr}")
        client.delete_log_stream(logGroupName=groupName, logStreamName=streamName)
