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
Retrieves parameters and outputs from a named CloudFormation stack and writes
environment variable export commands for specified values.

Invocation:

    cf-env.py STACK_NAME (VARNAME=ParmName | VARNAME=OutputName) ...

Where:

    STACK_NAME  identifies a CloudFormation stack accessible to the caller.
    VARNAME     is the desired name of an environment variable.
    ParmName    is the logical name of a stack parameter.
    OutputName  is the logical name (not export name) or a stack output.

    If there is no parameter/output with the specified name, it is silently
    ignored.

Example:

    Note that this example wraps the invocation in $(), which cause Bash to
    execute the commands and update its environment.

    $(cf-env.py ExampleSQS QUEUE_NAME=QueueName QUEUE_URL=QueueUrl)
"""

import boto3
import sys


def retrieve_stack_values(stack_name):
    """Retrieves the named stack's parameters and outputs.

       The output is a dictionary, where the key is the logical ID of the
       parameter/output, and the value is its value. Since logical IDs must
       be unique, there is no opportunity for losing information.
    """
    client = boto3.client('cloudformation')
    desc = client.describe_stacks(StackName=stack_name)
    stack = desc.get('Stacks')[0]
    result = {}
    for param in stack.get('Parameters', []):
        result[param['ParameterKey']] = param['ParameterValue']
    for output in stack.get('Outputs', []):
        result[output['OutputKey']] = output['OutputValue']
    return result


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    lookup = retrieve_stack_values(sys.argv[1])
    for arg in sys.argv[2:]:
        kv = arg.split('=')
        val = lookup.get(kv[1])
        if val:
            print("export " + kv[0] + "=" + val)
