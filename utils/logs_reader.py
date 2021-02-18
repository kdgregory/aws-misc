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
Can read a single stream, or all streams in the log group.

Invocation:

    logs_reader LOG_GROUP_NAME [ LOG_STREAM_NAME ... ]

Where:

    LOG_GROUP_NAME  is the group to read.
    LOG_STREAM_NAME is one or more log streams within that group to read. If
                    omitted, all streams are retrieved in order of last message
                    timestamp.

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
"""

import boto3
import json
import sys

from datetime import datetime, timezone


client = boto3.client('logs')


def retrieve_log_stream_names(log_group_name):
    """ Retrieves all of the log streams for a given log group. These streams are ordered
        by last event time (which implies that only streams with events are returned).
    """
    streams = []
    paginator = client.get_paginator('describe_log_streams')
    for page in paginator.paginate(logGroupName=log_group_name, orderBy='LastEventTime'):
        for stream in page['logStreams']:
            streams.append(stream['logStreamName'])
    return streams


def read_log_messages(log_group_name, log_stream_name):
    """ Retrieves all events from the specified log group/stream, formats the timestamp
        as an ISO-8601 string, and sorts them by timestamp.
    """
    events = []
    paginator = client.get_paginator('filter_log_events')
    for page in paginator.paginate(logGroupName=log_group_name, logStreamNames=[log_stream_name]):
        for event in page['events']:
            ts = event['timestamp']
            event['originalTimestamp'] = ts
            event['timestamp'] = datetime.fromtimestamp(ts / 1000.0, timezone.utc).isoformat()
            events.append(event)
    # this step may be unnecessary, but I don't see any ordering guarantees
    events.sort(key=lambda x: x['timestamp'])
    return events


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    group_name = sys.argv[1]
    if len(sys.argv) == 2:
        stream_names = retrieve_log_stream_names(group_name)
    else:
        stream_names = sys.argv[2:]
    for stream_name in stream_names:
        for event in read_log_messages(group_name, stream_name):
            print(json.dumps(event))

