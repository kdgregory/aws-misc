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

    This Lambda appends a newline to the end of the source records, first strippng
    any \n or \r characters from the end of the string. Leaves all other whitespace
    in place.
    """

import base64
import json
import logging


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


def lambda_handler(event, context):
    # print(f"event: \n {json.dumps(event)}")
    result = [process(rec) for rec in event['records']]
    # print(f"result: \n {json.dumps(result)}")
    LOGGER.info(f"processed {len(result)} records")
    return {"records": result}
    
    
def process(rec):
    """ Handles a single record. Transformation errors result in ProcessingFailed.
        Errors retrieving or decoding request cause function to abort, as those
        indicate a problem with Firehose.
        """
    record_id = rec['recordId']
    data = base64.b64decode(rec['data'])
    try:
        while data.endswith(b'\n') or data.endswith(b'\r'):
            data = data[:-1]
        data += b'\n'
        return {
            'recordId': record_id,
            'result': 'Ok',
            'data': base64.b64encode(data).decode()
        }
    except Exception as ex:
        return {
            'recordId': record_id,
            'result': 'ProcessingFailed',
            'data': base64.b64encode(data).decode()
        }
