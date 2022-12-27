# Copyright 2022 Keith D Gregory
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

""" This is used in an EventBridge pipeline, to extract log events from a
    CloudWatch Logs subscription, so that they can be stored as individual
    events on a destination stream.

    Along the way it it transforms the event to JSON (if it's not already) and
    adds information about the log stream and (for Lambdas) execution times.
    """

import base64
import gzip
import json
import logging

from datetime import datetime, timezone


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    logger.info(f"received {len(event)} messages from source")
    result = []
    for message in event:
        result += transform_messages(message)
    logger.info(f"produced {len(result)} messages")
    return result
    
    
def transform_messages(message):
    """ Handles a single Kinesis message from the source event.
        """
    data = base64.b64decode(message['data'])
    # CloudWatch Logs messages are always GZipped, but this is copy-paste code
    if data.startswith(b'\x1f\x8b'):
        data = gzip.decompress(data)
    payload = json.loads(data)
    if payload['messageType'] == 'DATA_MESSAGE':
        log_group = payload['logGroup']
        log_stream = payload['logStream']
        events = payload['logEvents']
        logger.debug(f"processing {len(events)} log events")
        return [transform_log_event(log_group, log_stream, event) for event in events]
    else:
        return []


def transform_log_event(log_group, log_stream, log_event):
    """ Processes a single log event from the subscription. The returned value
        is stringified JSON. If the source message can be parsed as JSON, it
        will be returned with the enhancements described below. If it can't be
        parsed as JSON, then a new JSON object will be created with a "message"
        key. In either case, the returned JSON will have a "cloudwatch" key that
        contains the log group and stream name, and the CloudWatch timestamp.
        WARNING: this will overwrite any prior "cloudwatcH" key.
        """
    message = log_event['message']
    try:
        result = json.loads(message)
    except:
        result = { "message": message }
    result['cloudwatch'] = {
        "log_group": log_group,
        "log_stream": log_stream,
        "id": log_event['id'],
        "timestamp": format_timestamp(log_event['timestamp']),
    }
    return result
    
    
def format_timestamp(timestamp):
    """ Utility function to take a Java-style timestamp (millis since epoch)
        and format it as an ISO-8601 string using the built-in datetime object.
        """
    if timestamp:
        dt = datetime.fromtimestamp(timestamp / 1000, timezone.utc)
        dt = dt.replace(microsecond=(1000 * (timestamp % 1000)))
        return dt.isoformat()
    else:
        return ""
    
