#!/usr/bin/env python3
################################################################################
# Copyright 2026 Keith D Gregory
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
Retrieves parameters and/or outputs from a named CloudFormation stack and writes
them as JSON, suitable for use by cf-deploy.py.

Invocation:

    cf-json.py [+params] [-outputs] STACK_NAME

Where:
    
    +params includes parameters in the result (they're normally omitted).
    -outputs excludes outputs from the result (they're normally included).
    STACK_NAME is the name or ARN of the stack to examine.
"""

import boto3
import json
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
    params = {}
    outputs = {}
    for param in stack.get('Parameters', []):
        params[param['ParameterKey']] = param['ParameterValue']
    for output in stack.get('Outputs', []):
        outputs[output['OutputKey']] = output['OutputValue']
    return params, outputs


if __name__ == "__main__":
    # argparse doesn't allow optional arguments that don't start with "-" so we have to parse ourselves
    use_params = False
    use_outputs = True
    stack_id = None
    for arg in sys.argv[1:]:
        if arg == "+params":
            use_params = True
        elif arg == "-outputs":
            use_outputs = False
        elif stack_id:
            print(__doc__, file=sys.stderr)
            sys.exit(1)
        else:
            stack_id = arg
    params, outputs = retrieve_stack_values(stack_id)
    result = {}
    if use_params:
        result.update(params)
    if use_outputs:
        result.update(outputs)
    print(json.dumps(result, indent=4))

