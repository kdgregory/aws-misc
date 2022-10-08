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

""" 
    Retrieves a Secrets Manager secret, and either returns a single value or
    writes commands to set environment variables with the values. Supports
    single-value secrets, and those containing a stringified JSON object.

    Invocation:

        sm-env.py SECRET_NAME (VARNAME | VARNAME=KEY ...)
        sm-val.py SECRET_NAME [KEY]

    Where:

        SECRET_NAME identifies the Secrets Manager secret. May be either the
                    name of the secret or its ARN.
        VARNAME     is the desired name of an environment variable.
        KEY         identifies a value within a JSON secret.

    There are four ways to invoke this function:

     - As sm-var.py, to output the entire value of the secret.
     - As sm-var.py, to output a keyed value from a JSON-encoded secret.
     - As sm-env.py, to output an environment variable assignment using
       the entire value of the secret.
     - As sm-env.py, to output one or more environment variable assignments
       using keys from within JSON-encoded secrets.

    Example: set standard Postgres environment variables based on the contents
    of an RDS-standard secret:

        $(sm-env.py DatabaseUserSecret \
                    PGHOST=host \
                    PGPORT=port \
                    PGUSER=username \
                    PGPASSWORD=password \
                    PGDATABASE=dbname)
    """

import boto3
import json
import os
import sys


def _check_usage(expected_arg_count=None):
    if (expected_arg_count is None) or (len(sys.argv) < expected_arg_count):
        print(__doc__, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    _check_usage(2)
    client = boto3.client('secretsmanager')
    secret_id = sys.argv[1]
    value = client.get_secret_value(SecretId=secret_id)['SecretString']

    if os.path.basename(__file__) == 'sm-env.py':
        _check_usage(3)
        if not "=" in sys.argv[2]:
            print(f"export {sys.argv[2]}={value}")
        else:
            lookup = json.loads(value)
            for arg in sys.argv[2:]:
                kv = arg.split('=')
                val = lookup.get(kv[1])
                if val:
                    print(f"export {kv[0]}={val}")
    elif os.path.basename(__file__) == 'sm-val.py':
        if len(sys.argv) == 2:
            print(value)
        else:
            lookup = json.loads(value)
            print(lookup[sys.argv[2]])
    else:
        _check_usage() # force exit
