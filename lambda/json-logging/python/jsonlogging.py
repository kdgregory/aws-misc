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

import json
import logging
import sys
import time
import traceback


class JSONFormatter:
    """A formatter for the Python logging module that converts a LogRecord into JSON.
    
    Output generally matches JSONLayout from https://github.com/kdgregory/log4j-aws-appenders.
    Supports an optional sub-object for application-defined tags, and one for lambda invocation
    parameters (the latter is populated by configure_logging()).
    """
    
    def __init__(self, tags=None, lambda_info=None):
        self.tags = tags
        self.lambda_info = lambda_info
    
    def format(self, record):
        result = {
            'timestamp':    time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) +
                            (".%03dZ" % (1000 * (record.created % 1))),
            'level':        record.levelname,
            'logger':       record.name,
            'message':      record.msg % record.args,
            'processId':    record.process,
            'thread':       record.threadName,
            'locationInfo': {
                            'fileName':     record.filename,
                            'lineNumber':   record.lineno
                            }
            }
        if self.tags:
            result['tags'] = self.tags
        if self.lambda_info:
            result['lambda'] = self.lambda_info
        if (record.exc_info):
            result['exception'] = traceback.format_exception(record.exc_info[0], record.exc_info[1], record.exc_info[2])
        return json.dumps(result)


def configure_logging(context=None, level=logging.INFO, tags=None):
    """Configures the root logger to use JSON output, adding tags and information
       retrieved from the Lambda context (if available)"""
    
    lambda_info = None
    if context:
        lambda_info = {}
        lambda_info['requestId']       = context.aws_request_id
        lambda_info['functionName']    = context.function_name
        lambda_info['functionVersion'] = context.function_version
    
    if tags:
        tags = tags.copy()
    
    formatter = JSONFormatter(tags, lambda_info)
    
    root = logging.getLogger()
    root.setLevel(level)
    if root.handlers:
        # for Lambda, the logger will be preconfigured with a formatter; replace it
        for handler in root.handlers:
            handler.setFormatter(formatter)
    else:
        # for everything else, we'll create a handler
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(formatter)
        root.addHandler(handler)
