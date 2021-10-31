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

    This Lambda appends a newline to the end of the source records if one isn't
    already there, stripping a \r\n or \r if those terminate the string.
    """

import base64
import json
import logging


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


def lambda_handler(event, context):
    # print(f"event: \n {json.dumps(event)}")
    result = [process(rec) for rec in event['records']]
    # print(f"result: \n {json.dumps(result)}")
    LOGGER.info(f"processed {len(result)} records")
    return {"records": result}
    
    
def process(rec):
    """ Handle a single record, passing it to transform() and returning the 
        expected dict. Marks the record as Dropped if transform() returns
        None, ProcessingFailed if it throws.
        """
    record_id = rec['recordId']
    try:
        data = base64.b64decode(rec['data'])
        transformed = transform(data)
        if transformed:
            return {
                'recordId': record_id,
                'result': 'Ok',
                'data': str(base64.b64encode(transformed), "utf-8")
            } 
        else:
            return {
                'recordId': record_id,
                'result': 'Dropped'
            }
    except Exception as ex:
        LOGGER.warn(f"exception processing record", exc_info=True)
        return {
            'recordId': record_id,
            'result': 'ProcessingFailed'
        }

    
def transform(data:bytes):
    """ Strips trailing \n and \r, and appends a single \n.
        """
    while data.endswith(b'\n') or data.endswith(b'\r'):
        data = data[:-1]
    data += b'\n'
    return data
