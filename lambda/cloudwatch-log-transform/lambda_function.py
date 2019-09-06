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
##
## This function is attached to a Kinesis stream that is the destination for a
## CloudWatch Logs subscription, to write the log events to a different stream.
## Along the way it transforms the event to JSON ## (if it's not already) and
## adds information about the log stream and (for Lambdas) execution times.
##
################################################################################

import base64
import boto3
import gzip
import json
import logging
import os
import re
import time

from datetime import datetime, timezone

logging.basicConfig()
logging.getLogger().setLevel(level=logging.INFO)

kinesisClient = boto3.client('kinesis')
kinesisStream = os.environ['DESTINATION_STREAM_NAME']

pythonLoggingRegex = re.compile(r'\[([A-Z]+)]\s+([0-9]{4}-.*Z)\s+([-0-9a-fA-F]{36})\s+(.*)')
lambdaStartRegex   = re.compile(r'START RequestId:\s+([-0-9a-fA-F]{36})\s+Version:\s+(.+)')
lambdaFinishRegex  = re.compile(r'END RequestId:\s+([-0-9a-fA-F]{36})')
lambdaReportRegex  = re.compile(r'REPORT RequestId:\s+([-0-9a-fA-F]{36})\s+Duration:\s+([0-9.]+)\s+ms\s+Billed Duration:\s+([0-9]+)\s+ms\s+Memory Size:\s+([0-9]+)\s+MB\s+Max Memory Used:\s+([0-9]+)\s+MB')


def lambda_handler(event, context):
    outputMessages = []
    for record in event['Records']:
        outputMessages = outputMessages + process_input_record(record)
    logging.info(f'total number of messages to output: {len(outputMessages)}')
    logging.debug(f'output messages: {json.dumps(outputMessages)}')
    write_to_kinesis(outputMessages)

## each input record may be a data message with multiple log events, or a control message
## that indicates the start of processing; this function processes the first and ignores
## the second (as well as any other messages that might be on the stream)
def process_input_record(record):
    try:
        payload = record['kinesis']['data']
        decoded = gzip.decompress(base64.b64decode(payload))
        data = json.loads(decoded)
        message_type = data.get('messageType')
        if message_type == 'DATA_MESSAGE':
            logGroup = data['logGroup']
            logStream = data['logStream']
            events = data.get('logEvents', [])
            logging.info(f'processing {len(events)} events from group "{logGroup}" / stream "{logStream}"')
            logging.debug(f'input messages: {json.dumps(events)}')
            return [transform_log_event(logGroup, logStream, event) for event in events]
        elif message_type == 'CONTROL_MESSAGE':
            logging.info('skipping control message')
        elif message_type:
            logging.warn(f'unexpected message type: {message_type}')
    except:
        logging.error(f'failed to process record; keys = {record.keys()}', exc_info=True)
    # fall-through for any unprocessed messages (exception or unhandled message type)
    return []


## turns the message into JSON if it isn't already, recognizing standard logging
## formats, and adding tracking fields
def transform_log_event(logGroup, logStream, event):
    message = event.get('message', '').strip()
    result = try_parse_json(message)
    if not result:
        result = try_parse_python_log(message)
    if not result:
        result = {
            'level': 'INFO',
            'message': message
        }
    
    result['cloudwatch'] = {
        'logGroup': logGroup,
        'logStream': logStream
    }
    opt_add_timestamp(result, event)
    opt_add_lambda_status(result, message)
    return result


## attempts to parse the passed message as JSON, returning the parsed representation
## if successful; otherwise returns a JSON object with a single "message" element
def try_parse_json(message):
    if message.startswith('{') and message.endswith('}'):
        try:
            return json.loads(message)
        except:
            pass


## attempts to parse the passed message as output from the Lambda Python logger,
## as documented here: https://docs.aws.amazon.com/lambda/latest/dg/python-logging.html
def try_parse_python_log(message):
    match = pythonLoggingRegex.match(message)
    if match:
        return {
            'level':        match.group(1),
            'timestamp':    match.group(2),
            'lambda':       { 'requestId': match.group(3) },
            'message':      match.group(4)
        }


## if the passed data field already has a "timestamp" element, it's returned unchanged
## otherwise the passed event timestamp is formatted and added to the message
def opt_add_timestamp(data, event):
    if data.get('timestamp'):
        return
    dt = datetime.fromtimestamp(event['timestamp'] / 1000.0, tz=timezone.utc)
    data['timestamp'] = dt.isoformat()


## if the message matches one of the Lambda status messages, adds extracted information
def opt_add_lambda_status(result, message):
    try:
        if message.startswith('START RequestId:'):
            match = lambdaStartRegex.match(message)
            if match:
                result['lambda'] = {
                    'requestId':    match.group(1),
                    'version':      match.group(2)
                }
        elif message.startswith('END RequestId:'):
            match = lambdaFinishRegex.match(message)
            if match:
                result['lambda'] = {
                    'requestId':    match.group(1)
                }
        elif message.startswith('REPORT RequestId:'):
            match = lambdaReportRegex.match(message)
            if match:
                result['lambda'] = {
                    'requestId':    match.group(1),
                    'durationMs':   float(match.group(2)),
                    'billedMs':     float(match.group(3)),
                    'maxMemoryMb':  int(match.group(4)),
                    'usedMemoryMb': int(match.group(5))
                }
    except:
        pass


## makes a best-effort attempt to write all messages to Kinesis, batching them
## as needed to meet the limits of PutRecords
def write_to_kinesis(listOfEvents):
    records = transform_records(listOfEvents)
    while records:
        records = process_batch(records)
        if (records):
            time.sleep(2) # an arbitrary sleep; we should rarely hit this
    return


## packages the passed log events into records for PutRecords
def transform_records(listOfEvents):
    records = []
    for event in listOfEvents:
        partitionKey = event.get('cloudwatch', {}).get('logStream', 'DEFAULT')
        records.append({
            'PartitionKey': partitionKey,
            'Data': json.dumps(event)
        })
    return records


## forms a batch from the provided records and attempts to send it; any records
## that couldn't fit in the batch will be returned, as well as any that couldn't
## be sent (we return unattempted records first to give them the best chance of
## being sent if there are persistent errors)
def process_batch(records):
    toBeSent, toBeReturned = build_batch(records)
    logging.info(f'sending batch of {len(toBeSent)} records with {len(toBeReturned)} remaining')
    try:
        response = kinesisClient.put_records(
            StreamName=kinesisStream,
            Records=toBeSent
        )
        return toBeReturned + process_response(response, toBeSent)
    except kinesisClient.exceptions.ProvisionedThroughputExceededException:
        logging.warn(f'received throughput exceeded on stream {kinesisStream}; retrying all messages')
        return toBeSent + toBeReturned


## creates a batch of records based on Kinesis limits; returns both the batch
## and any remaining records that didn't fit in the batch
def build_batch(records):
    recCount = 0
    byteCount = 0
    
    while recCount < min(len(records), 500) and byteCount < 1048576:
        record = records[recCount]
        recCount += 1
        byteCount += len(record['Data']) + len(record['PartitionKey'])
    
    # we already added the record before we knew the size, so we'll compensate
    if byteCount > 1048576:
        recCount = recCount - 1
    
    # this should never happen: it would require a max-size log event and a
    # long partition key
    if recCount == 0:
        logging.warn("throwing out too-long message")
        return [], records[1:]
    
    return records[:recCount], records[recCount:]


## examines the response from a send command, and returns those records that were
## rejected
def process_response(response, records):
    if response['FailedRecordCount'] == 0:
        return []
    
    result = []
    droppedRecordCount = 0
    for ii in range(len(response['Records'])):
        entry = response['Records'][ii]
        errorCode = entry.get('ErrorCode')
        if errorCode == 'ProvisionedThroughputExceededException':
            result.append(records[ii])
        elif errorCode:
            droppedRecordCount += 1
    
    if droppedRecordCount > 0:
        logging.warn(f'dropped {droppedRecordCount} records due to internal errors')
    if len(result) > 0:
        logging.info(f"requeueing {len(result)} records due to throughput-exceeded")
    
    return result
