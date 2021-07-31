# Copyright 2019-2021 Keith D Gregory
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
import os
import random
import time
import sys

from datetime import datetime, timezone
from datetime import timedelta


def lambda_handler(event, context):
    client = boto3.client('logs')
    limit = int(os.environ.get('MAX_LOG_GROUPS', "1000000"))
    for group in retrieve_log_groups(client, limit):
        try:
            process_log_group(client, group)
        except:
            print(f"exception while processing log group {group.get('logGroupName')}: {sys.exc_info()[1]}; skipping to next")


def process_log_group(client, group):
    group_name = group['logGroupName']
    retention = group.get('retentionInDays')
    print(f"examining {group_name}, retention period = {retention}")
    if (retention == None):
        return
    retention_limit = datetime.now(tz=timezone.utc) - timedelta(days=retention)
    for stream in retrieve_log_streams(client, group_name):
        process_log_stream(client, group_name, stream, retention_limit)
        time.sleep(0.1)


def process_log_stream(client, group_name, stream, retention_limit):
    stream_name = stream['logStreamName']
    creation_time = datetime.fromtimestamp(stream['creationTime']/1000, timezone.utc)
    if (creation_time > retention_limit):
        return
    events = client.get_log_events(logGroupName=group_name, logStreamName=stream_name, limit=10).get('events')
    if events:
        return
    print(f"deleting {group_name} / {stream_name}: "
                f"created {creation_time.isoformat(sep=' ', timespec='seconds')}, "
                f"horizon {retention_limit.isoformat(sep=' ', timespec='seconds')}")
    client.delete_log_stream(logGroupName=group_name, logStreamName=stream_name)


def retrieve_log_groups(client, limit):
    result = []
    paginator = client.get_paginator('describe_log_groups')
    itx = paginator.paginate()
    for page in itx:
        for group in page['logGroups']:
            result.append(group)
        time.sleep(0.2)
    random.shuffle(result)
    if len(result) > limit:
        print(f"retrieved {len(result)} log groups; limiting to {limit}")
        return result[:limit]
    else:
        print(f"retrieved {len(result)} log groups")
        return result


def retrieve_log_streams(client, group_name):
    result = []
    paginator = client.get_paginator('describe_log_streams')
    itx = paginator.paginate(logGroupName=group_name)
    for page in itx:
        for stream in page['logStreams']:
            result.append(stream)
        time.sleep(0.2)
    return result
