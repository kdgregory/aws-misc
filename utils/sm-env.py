#!/usr/bin/env python3
################################################################################
# Copyright 2022 Keith D Gregory
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
#
# Retrieves a Secrets Manager secret and writes commands to set environment
# variables with the values. Supports single-value secrets, or those containing
# a stringified JSON object.
#
# Invocation:
#
#   rm-env.py SECRET_NAME (VARNAME | VARNAME=KEY ...)
#
# Where:
#
#   SECRET_NAME identifies the Secrets Manager secret. May be either the
#               name of the secret or its ARN.
#   VARNAME     is the desired name of an environment variable.
#   KEY         identifies a value within a JSON secret.
#
#   There are two ways to invoke this function:
#
#    - If you provide a single variable name, by itself, then it is set
#      to the entire secret value.
#    - If you provide a series of VARNAME=KEY pairs, then the secret is
#      assumed to contain a stringified JSON object. It is parsed, and
#      each variable is set to the value of the specified key. If the
#      key does not exist, this program emits an empty assignment.
#
# Example:
#
#   Note that this example wraps the invocation in $(), which cause Bash to
#   execute the commands and update its environment.
#
#   $(sm-env.py DatabaseConnection PGHOST=QueueName QUEUE_URL=QueueUrl)
#
################################################################################

import boto3
import json
import sys


def retrieve_secret(secret_id):
    """ Retrieves the secret's value.
    """
    client = boto3.client('secretsmanager')
    return client.get_secret_value(SecretId=secret_id)['SecretString']


if __name__ == "__main__":
    value = retrieve_secret(sys.argv[1])
    if not "=" in sys.argv[2]:
        print(f"export {sys.argv[2]}={value}")
    else:
        lookup = json.loads(value)
        for arg in sys.argv[2:]:
            kv = arg.split('=')
            val = lookup.get(kv[1])
            if val:
                print(f"export {kv[0]}={val}")
