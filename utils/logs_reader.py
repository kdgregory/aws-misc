#!/usr/bin/env python3
################################################################################
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

"""
A command-line utility to retrieve log messages from a CloudWatch Logs log group.
Can read a single stream, or a subset of streams in a single log group.

Invocation:

    logs_reader LOG_GROUP_NAME [ LOG_STREAM_PREFIX ... ]

Where:

    LOG_GROUP_NAME      is the group to read.
    LOG_STREAM_PREFIX   identifies one or more log streams within that group to read.
                        If provided as a prefix, all log streams with that prefix are
                        read; if omitted, all log streams for the log group are read.

Notes:

    Output is JSON, with the following fields:

        logStreamName       the name of the stream that the message was read from
                            (useful if processing multiple streams).
        eventId             a unique identifier for the event.
        timestamp           the message timestamp, as an ISO-8601 UTC string.
        originalTimestamp   the message timestamp, as millis since epoch
        ingestionTime       the time the message was ingested by CloudWatch, as
                            millis since epoch.
        message             the logged message.

    All messages for a single log stream are output before moving on to the next.

    Messages are output in timestamp order, and when processing multiple streams
    the streams are ordered based on the timestamp of their last message.
"""

import boto3
import json
import sys

from datetime import datetime, timezone


client = boto3.client('logs')


def retrieve_log_stream_names(log_group_name, prefixes=None):
    """ Retrieves streams for the given log group with the specified prefixes.
        If no prefixes are provided, returns all streams for the log group.
        Streams will be sorted by the timestamp of the last log event.
    """
    streams = []
    paginator = client.get_paginator('describe_log_streams')
    if prefixes:
        for prefix in prefixes:
            for page in paginator.paginate(logGroupName=log_group_name, logStreamNamePrefix=prefix):
                streams += page['logStreams']
    else:
        for page in paginator.paginate(logGroupName=log_group_name):
            streams += page['logStreams']
    streams.sort(key=lambda x: x['lastEventTimestamp'])
    return [x['logStreamName'] for x in streams]


def read_log_messages(log_group_name, log_stream_name):
    """ Retrieves all events from the specified log group/stream, formats the timestamp
        as an ISO-8601 string, and sorts them by timestamp.

        Note: filter_log_events() takes an excessive amount of time if there are a large
        number of streams, even though we're only selecting from one, so instead we use 
        get_log_events(). However, Boto doesn't provide a paginator for it, so we have to
        handle the pagination ourselves. Fun!
    """
    events = []
    request = {
        'logGroupIdentifier': log_group_name,
        'logStreamName': log_stream_name,
        'startTime': 0,
        'startFromHead': True
    } 
    while True:
        page = client.get_log_events(**request)
        if page['nextForwardToken'] == request.get('nextToken'):
            break;
        request['nextToken'] = page['nextForwardToken']
        for event in page['events']:
            ts = event['timestamp']
            event['originalTimestamp'] = ts
            event['timestamp'] = datetime.fromtimestamp(ts / 1000, timezone.utc).isoformat()
            events.append(event)
    events.sort(key=lambda x: x['timestamp'])   # API doesn't guarantee order
    return events

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    group_name = sys.argv[1]
    if len(sys.argv) == 2:
        prefixes = None
    else:
        prefixes = sys.argv[2:]
    stream_names = retrieve_log_stream_names(group_name, prefixes)
    for stream_name in stream_names:
        for event in read_log_messages(group_name, stream_name):
            print(json.dumps(event))

