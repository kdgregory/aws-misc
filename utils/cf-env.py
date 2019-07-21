#!/usr/bin/env python3
################################################################################
#
# Retrieves parameters and outputs from a named CloudFormation stack and writes
# environment variable export commands for specified values.
#
# Invocation:
#
#   cf-env.py STACK_NAME (VARNAME=ParmName | VARNAME=OutputName) ...
#
# Where:
#
#   STACK_NAME  identifies a CloudFormation stack accessible to the caller.
#   VARNAME     is the desired name of an environment variable.
#   ParmName    is the logical name of a stack parameter.
#   OutputName  is the logical name (not export name) or a stack output.
#
#   If there is no parameter/output with the specified name, it is silently
#   ignored.
#
# Example:
#
#   Note that this example wraps the invocation in $(), which cause Bash to
#   execute the commands and update its environment.
#
#   $(cf-env.py ExampleSQS QUEUE_NAME=QueueName QUEUE_URL=QueueUrl)
#
# Programmatic use:
# 
#   The function retrieveStackValues() retrieves the values for a stack and
#   returns them as a dictionary.
#
################################################################################

import boto3
import sys


def retrieveStackValues(stack_name):
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
    lookup = retrieveStackValues(sys.argv[1])
    for arg in sys.argv[2:]:
        kv = arg.split('=')
        val = lookup.get(kv[1])
        if val:
            print("export " + kv[0] + "=" + val)
