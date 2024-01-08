# Copyright 2023, Keith D Gregory
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


import boto3
import json
import logging
import re
import time


logger = logging.getLogger("KinesisReader")
logger.setLevel(logging.DEBUG)


class Record:
    """ An internal helper that holds retrieved messages
        """

    def __init__(self):
        pass


class KinesisReader:

    def __init__(self, client, stream, log_actions=False):
        """ Initializes a new reader.

            client
            stream
            log_actions
            """
        self._client = client
        if stream.startswith("arn:"):
            self._stream_name = re.sub(r".*:", "", stream)
            self._stream_param = { "StreamARN": stream }
        else:
            self._stream_name = stream
            self._stream_param = { "StreamName": stream }
        self._log_actions = log_actions
