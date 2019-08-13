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
## This function is attached to a CloudWatch Logs subscription to write the log
## events to a Kinesis stream. Along the way it transforms the event to JSON
## (if it's not already) and adds ## information about the log stream and (for
## Lambdas) execution times
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
kinesisStream = os.environ['STREAM_NAME']

lambdaReportRegex = re.compile(r'REPORT RequestId: (.{36})\s+Duration: ([0-9.]+) ms\s+Billed Duration: ([0-9]+) ms\s+Memory Size: ([0-9]+) MB\s+Max Memory Used: ([0-9]+) MB')


def lambda_handler(event, context):
    payload = event['awslogs']['data']
    decoded = gzip.decompress(base64.b64decode(payload))
    data = json.loads(decoded)
    logGroup = data['logGroup']
    logStream = data['logStream']
    events = data.get('logEvents', [])
    logging.info(f'processing {len(events)} events from group "{logGroup}", stream "{logStream}"')
    logging.debug("input messages: " + json.dumps(events))
    outputMessages = [transformLogEvent(logGroup, logStream, event) for event in events]
    logging.debug("output messages: " + json.dumps(outputMessages))
    writeToKinesis(logStream, outputMessages)
    return


## events that are already formatted as JSON are returned unchanged, those that aren't
## are wrapped in JSON; all events get annotated with log group and log stream
def transformLogEvent(logGroup, logStream, event):
    result = tryParseJson(event['message'])
    result['cloudwatch'] = {
        'logGroup': logGroup,
        'logStream': logStream
    }
    optAddTimestamp(result, event)
    optAddLambdaReport(result, event)
    return result


## attempts to parse the passed message as JSON, returning the parsed representation
## if successful; otherwise returns a JSON object with a single "message" element
def tryParseJson(message):
    trimmed = message.strip()
    if trimmed[0] == '{' and trimmed[-1] == '}':
        try:
            return json.loads(trimmed)
        except:
            pass # fall through to non-JSON return
    return {
        'message': message
    }


## if the passed data field already has a "timestamp" element, it's returned unchanged
## otherwise the passed event timestamp is formatted and added to the message
def optAddTimestamp(data, event):
    if data.get('timestamp'):
        return
    dt = datetime.fromtimestamp(event['timestamp'] / 1000.0, tz=timezone.utc)
    data['timestamp'] = dt.isoformat()
    return


## if the event is a Lambda execution report, the statistics are parsed out and
## added as a sub-object within the result
def optAddLambdaReport(result, event):
    eventMessage = event['message']
    if not eventMessage.startswith("REPORT RequestId"):
        return
    try:
        match = lambdaReportRegex.match(eventMessage)
        if match:
            result['lambdaReport'] = {
                'requestId':    match.group(1),
                'durationMs':   float(match.group(2)),
                'billedMs':     float(match.group(3)),
                'maxMemoryMb':  int(match.group(4)),
                'usedMemoryMb': int(match.group(5))
            }
    except:
        logging.error(f'failed to parse Lambda report from {eventMessage}', exc_info=True)


## makes a best-effort attempt to write all messages to Kinesis, batching them
## as needed to meet the limits of PutRecords
def writeToKinesis(partitionKey, listOfEvents):
    records = transformToRecords(partitionKey, listOfEvents)
    while records:
        records = processBatch(records)
        if (records):
            time.sleep(2) # an arbitrary sleep; we should rarely hit this
    return


## packages the passed log events into records for PutRecords
def transformToRecords(partitionKey, listOfEvents):
    records = []
    for event in listOfEvents:
        records.append({
            'PartitionKey': partitionKey,
            'Data': json.dumps(event)
        })
    return records


## forms a batch from the provided records and attempts to send it; any records
## that couldn't fit in the batch will be returned, as well as any that couldn't
## be sent (we return unattempted records first to give them the best chance of
## being sent if there are persistent errors)
def processBatch(records):
    toBeSent, toBeReturned = buildBatch(records)
    logging.info(f'sending batch of {len(toBeSent)} records with {len(toBeReturned)} remaining')
    try:
        response = kinesisClient.put_records(
            StreamName=kinesisStream,
            Records=toBeSent
        )
        return toBeReturned + processResponse(response, toBeSent)
    except kinesisClient.exceptions.ProvisionedThroughputExceededException:
        logging.warn(f'received throughput exceeded on stream {kinesisStream}; retrying all messages')
        return toBeSent + toBeReturned


## creates a batch of records based on Kinesis limits; returns both the batch
## and any remaining records that didn't fit in the batch
def buildBatch(records):
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
def processResponse(response, records):
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
