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

""" This function is attached to a Kinesis stream that is the destination for a
    CloudWatch Logs subscription, to write the log events to a different stream.
    ## Along the way it transforms the event to JSON ## (if it's not already) and
    ## adds information about the log stream and (for Lambdas) execution times.
    """


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

## fail fast on bad configuration
kinesis_client = boto3.client('kinesis')
kinesis_stream = os.environ['DESTINATION_STREAM_NAME']


python_logging_regex    = re.compile(r'\[([A-Z]+)]\s+([0-9]{4}-.*Z)\s+([-0-9a-fA-F]{36})\s+(.*)')

lambda_start_regex      = re.compile(r'START RequestId:\s+([-0-9a-fA-F]{36})\s+Version:\s+(.+)')
lambda_finish_regex     = re.compile(r'END RequestId:\s+([-0-9a-fA-F]{36})')
lambda_report_regex     = re.compile(r'REPORT RequestId:\s+([-0-9a-fA-F]{36})\s+Duration:\s+([0-9.]+)\s+ms\s+Billed Duration:\s+([0-9]+)\s+ms\s+Memory Size:\s+([0-9]+)\s+MB\s+Max Memory Used:\s+([0-9]+)\s+MB')
lambda_extended_regex   = re.compile(r'.*Init Duration:\s+([0-9.]+)\s+ms')
lambda_xray_regex       = re.compile(r'.*XRAY TraceId:\s+([0-9a-fA-F-]+)\s+SegmentId:\s+([0-9a-fA-F]+)\s+Sampled:\s+(true|false)')


def lambda_handler(event, context):
    output_messages = extract_messages(event)
    logging.info(f'total number of messages to output: {len(output_messages)}')
    logging.debug(f'output messages: {json.dumps(output_messages)}')
    write_to_kinesis(output_messages)


def extract_messages(event):
    """ Source records may contain multiple log messages, so we can't just use a list
        comprehension to extract them. We also want to skip control records, and any
        records that we can't process for unforeseen reasons. Thus this function.
        """
    output_messages = []
    for record in event['Records']:
        output_messages += process_input_record(record)
    return output_messages


def process_input_record(record):
    try:
        payload = record['kinesis']['data']
        decoded = gzip.decompress(base64.b64decode(payload))
        data = json.loads(decoded)
        message_type = data.get('messageType')
        if message_type == 'DATA_MESSAGE':
            log_group = data['logGroup']
            log_stream = data['logStream']
            events = data.get('logEvents', [])
            logging.info(f'processing {len(events)} events from group "{log_group}" / stream "{log_stream}"')
            logging.debug(f'input events: {json.dumps(events)}')
            return [transform_log_event(log_group, log_stream, event) for event in events]
        elif message_type == 'CONTROL_MESSAGE':
            logging.debug('skipping control message')
        elif message_type:
            logging.warning(f'unexpected message type: {message_type}')
    except:
        logging.error(f'failed to process record; keys = {record.keys()}', exc_info=True)
    # fall-through for any unprocessed messages (exception or unhandled message type)
    return []


def transform_log_event(log_group, log_stream, event):
    """ Turns the message into JSON if it isn't already, recognizing standard logging
        formats; adds tracking fields.
        """
    message = event.get('message', '').strip()
    result = try_parse_json(message)
    if not result:
        result = try_parse_python_log(message)
    if not result:
        result = try_parse_lambda_status(message)
    if not result:
        result = {
            'level': 'INFO',
            'message': message
        }

    result['source'] = {
        'logGroup': log_group,
        'logStream': log_stream
    }
    opt_add_timestamp(result, event)
    return result


def try_parse_json(message):
    if message.startswith('{') and message.endswith('}'):
        try:
            return json.loads(message)
        except:
            pass


def try_parse_python_log(message):
    """ Attempts to parse the passed message as output from the Lambda Python logger, as
        documented here: https://docs.aws.amazon.com/lambda/latest/dg/python-logging.html
        """
    match = python_logging_regex.match(message)
    if match:
        return {
            'level':        match.group(1),
            'timestamp':    match.group(2),
            'lambda':       { 'requestId': match.group(3) },
            'message':      match.group(4)
        }


def try_parse_lambda_status(message):
    """ Attempts to parse the message as one of the standard Lambda status messages.
        """
    try:
        if message.startswith('START RequestId:'):
            match = lambda_start_regex.match(message)
            if match:
                data = {
                    'requestId':    match.group(1),
                    'version':      match.group(2)
                }
        elif message.startswith('END RequestId:'):
            match = lambda_finish_regex.match(message)
            if match:
                data = {
                    'requestId':    match.group(1)
                }
        elif message.startswith('REPORT RequestId:'):
            message = message.replace('\n', '\t')
            match = lambda_report_regex.match(message)
            if match:
                data = {
                    'requestId':    match.group(1),
                    'durationMs':   float(match.group(2)),
                    'billedMs':     float(match.group(3)),
                    'maxMemoryMb':  int(match.group(4)),
                    'usedMemoryMb': int(match.group(5))
                }
                # initialization stats are only reported for first invocation
                match = lambda_extended_regex.match(message)
                if match:
                    data['initializationMs'] = float(match.group(1))
                # x-ray stats are only reported if enabled
                match = lambda_xray_regex.match(message)
                if match:
                    data['xrayTraceId'] = match.group(1)
                    data['xraySegment'] = match.group(2)
                    data['xraySampled'] = match.group(3)
        if data:
            return {
                'level':   'INFO',
                'message': message,
                'lambda':  data
            }
    except:
        pass


def opt_add_timestamp(data, event):
    """ If the passed data field already has a "timestamp" element, it's returned
        unchanged. Otherwise the log event's timestamp is formatted and added to
        the message.
        """
    if data.get('timestamp'):
        return
    dt = datetime.fromtimestamp(event['timestamp'] / 1000.0, tz=timezone.utc)
    data['timestamp'] = dt.isoformat()


def write_to_kinesis(listOfEvents):
    """ Makes a best-effort attempt to write all messages to Kinesis, batching them
        as needed to meet the limits of PutRecords.
        """
    records = prepare_records(listOfEvents)
    while records:
        records = process_batch(records)
        if (records):
            time.sleep(2) # an arbitrary sleep; we should rarely hit this
    return


def prepare_records(listOfEvents):
    records = []
    for event in listOfEvents:
        partition_key = event.get('cloudwatch', {}).get('logStream', 'DEFAULT')
        records.append({
            'PartitionKey': partition_key,
            'Data': json.dumps(event)
        })
    return records


def process_batch(records):
    """ Forms a batch from the provided records and attempts to send it; any records
        that won't fit in the batch will be returned, as well as any that couldn't
        be sent (we return unattempted records first to give them the best chance of
        being sent if there are persistent errors).
        """
    to_be_sent, to_be_returned = build_batch(records)
    logging.info(f'sending batch of {len(to_be_sent)} records with {len(to_be_returned)} remaining')
    try:
        response = kinesis_client.put_records(
            StreamName=kinesis_stream,
            Records=to_be_sent
        )
        return process_response(response, to_be_sent) + to_be_returned
    except kinesis_client.exceptions.ProvisionedThroughputExceededException:
        logging.warn(f'received throughput-exceeded on stream {kinesis_stream}; retrying all messages')
        return to_be_sent + to_be_returned


def build_batch(records):
    """ Creates a batch of records based on Kinesis limits; returns both the batch
        and any remaining records that didn't fit in the batch.
        """
    rec_count = 0
    byte_count = 0

    while rec_count < min(len(records), 500) and byte_count < 1048576:
        record = records[rec_count]
        rec_count += 1
        byte_count += len(record['Data']) + len(record['PartitionKey'])

    # we already added the record before we knew the size, so we'll compensate
    if byte_count > 1048576:
        rec_count = rec_count - 1

    # this should never happen: it would require a max-size log event and a
    # long partition key
    if rec_count == 0:
        logging.warn('throwing out too-long message')
        return [], records[1:]

    return records[:rec_count], records[rec_count:]


def process_response(response, records):
    """ Examines the response from PutRecords, returning any records that couldn't be sent.
        """
    if response['FailedRecordCount'] == 0:
        return []

    result = []
    dropped_record_count = 0
    for ii in range(len(response['Records'])):
        entry = response['Records'][ii]
        errorCode = entry.get('ErrorCode')
        if errorCode == 'ProvisionedThroughputExceededException':
            result.append(records[ii])
        elif errorCode:
            dropped_record_count += 1

    if dropped_record_count > 0:
        logging.warn(f'dropped {dropped_record_count} records due to Kinesis internal errors')
    if len(result) > 0:
        logging.info(f'requeueing {len(result)} records due to throughput-exceeded')

    return result
