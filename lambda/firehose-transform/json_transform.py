# Copyright 2021 Keith D Gregory
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


""" Kinesis Firehose Transformation Lambda.

    This Lambda expects incoming JSON data, which may be GZipped. It reformats
    that JSON as NDJSON, and provides a hook for dropping records.
    """

import base64
import gzip
import json
import logging
import os


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


def lambda_handler(event, context):
    # print(f"event: \n {json.dumps(event)}")
    result = [process(rec) for rec in event['records']]
    # print(f"result: \n {json.dumps(result)}")
    LOGGER.info(f"processed {len(result)} records: {summarize(result)}")
    return {"records": result}


def process(rec):
    record_id = rec['recordId']
    data = base64.b64decode(rec['data'])
    try:
        result = transform(data)
        if result:
            return {
                'recordId': record_id,
                'result': 'Ok',
                'data': base64.b64encode(result).decode()
            }
        else:
            return {
                'recordId': record_id,
                'result': 'Dropped'
            }
    except Exception as ex:
        if log_failures():
            LOGGER.debug(f"unable to process: {data}")
        return {
            'recordId': record_id,
            'result': 'ProcessingFailed',
            'data': base64.b64encode(data).decode()
        }


def transform(data):
    if data.startswith(b'\x1f\x8b'):
         data = gzip.decompress(data)
    parsed = json.loads(data.decode())
    if should_drop(parsed):
        return None
    reformatted = (json.dumps(parsed) + "\n")
    return reformatted.encode()


def should_drop(data):
    """ Implement this to filter records.
        """
    return False


def log_failures():
    # this is a function so that the envar can be overridden for testing
    return not not os.getenv("LOG_FAILURES")


def summarize(result):
    counts = { 'Ok': 0, 'Dropped': 0, 'ProcessingFailed': 0 }
    for rec in result:
        status = rec['result']
        counts[status] = counts[status] + 1
    return f"{counts['Ok']} successful, {counts['Dropped']} dropped, {counts['ProcessingFailed']} failed"
