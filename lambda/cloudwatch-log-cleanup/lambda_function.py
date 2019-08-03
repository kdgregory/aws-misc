# Copyright 2019 Keith D Gregory
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
################################################################################
#
# Deletes empty CloudWatch log streams that are older than their group's
# retention period.
#
################################################################################

import boto3
import time
from datetime import datetime
from datetime import timedelta

client = boto3.client('logs')

def lambda_handler(event, context):
    paginator = client.get_paginator('describe_log_groups')
    itx = paginator.paginate()
    for page in itx:
        for group in page['logGroups']:
            processLogGroup(group['logGroupName'], group.get('retentionInDays'))

def processLogGroup(groupName, retentionInDays):
    if (retentionInDays == None):
        return
    retentionLimit = (datetime.utcnow() - timedelta(days=retentionInDays) - timedelta(days=1)).timestamp()
    retentionLimitStr = time.asctime(time.gmtime(retentionLimit))
    print(f"examining {groupName}, retention period = {retentionInDays}, retention limit = {retentionLimitStr}")
    paginator = client.get_paginator('describe_log_streams')
    itx = paginator.paginate(logGroupName=groupName)
    for page in itx:
        for stream in page['logStreams']:
            processLogStream(groupName, stream['logStreamName'], stream['creationTime']/1000, retentionLimit)

def processLogStream(groupName, streamName, creationTime, retentionLimit):
    if (creationTime > retentionLimit):
        return
    events = client.get_log_events(logGroupName=groupName, logStreamName=streamName, limit=10).get('events')
    if events:
        return
    creatonTimeStr = time.asctime(time.gmtime(creationTime))
    print(f"deleting {groupName} / {streamName}: created {creatonTimeStr}")
    client.delete_log_stream(logGroupName=groupName, logStreamName=streamName)
