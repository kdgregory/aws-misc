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

Assumes a role, with optional MFA code, and either starts a new shell or runs
an arbitrary command using that role. Attempts to find the maximum allowed role
duration, by starting at 8 hours and working down.

Invocation:

    assume-role.py (ROLE_NAME | ROLE_ARN) [ MFA_CODE ]
    run-with-role.py (ROLE_NAME | ROLE_ARN) [ MFA_CODE ] COMMAND

Where:

    ROLE_NAME   is the simple name (including path) of an assumable role in
                the current account.
    ROLE_ARN    is the ARN of an assumable role from any account.
    MFA_CODE    is the 6-digit code from a virtual MFA device.
    COMMAND     is an arbitrary command.

Caveats:

    Only supports virtual MFA devices (this is because hardware devices are
    identified differently).

    For run-with-role, if your command name is a six-digit number, it will
    be interpreted as an MFA code. Unlikely.

    For assume-role, if you load your AWS credentials in .bashrc, they'll
    overwrite the assumed-role credentials. Don't do this.
"""

import boto3
import json
import os
import re
import sys
import uuid

from botocore.exceptions import ClientError

iam_client = boto3.client('iam')
sts_client = boto3.client('sts')


def lookup_role_arn(roleName):
    """ Returns the ARN for a role with the given name, None if it doesn't exist.

        The name should include any path (eg: "/service-role/Foo", but it will be
        matched even if the path is omitted (although you may get the wrong role).
    """
    lastSlash = roleName.rfind("/")
    if lastSlash >= 0:
        prefix = roleName[:lastSlash+1]
        baseName = roleName[lastSlash+1:]
    else:
        prefix = "/"
        baseName = roleName
    for page in iam_client.get_paginator('list_roles').paginate(PathPrefix=prefix):
        for role in page['Roles']:
            if baseName == role['RoleName']:
                return role['Arn']
    raise Exception(f'Unable to find role with name "{roleName}"')


def generate_session_name():
    """ Creates a session name based based on the account and name of the invoking
        user (if known) and a UUID.
    """
    invokerArn = sts_client.get_caller_identity()['Arn']
    matched = re.fullmatch(r"arn:aws:iam::([0-9]+):user/(.*)", invokerArn)
    if matched:
        return matched.group(1) + "-" + matched.group(2) + "-" + str(uuid.uuid4())
    else:
        return str(uuid.uuid4())


# this variable is a hack that lets us report the role duration from CLI invocation
actualDuration = None

def assume_role(arnOrName, mfaCode=None, desiredDuration=3600, durationRatio=None):
    """ Assumes a role and returns its credentials.

        Arguments:
            arnOrName       - May be passed either a role name in the current account
                              (in which case the ARN is retrieved) or an ARN (which
                              may belong to the current account or another account).
            mfaCode         - Optional: if present, the user's virtual MFA device is
                              retrieved and passed to the request with this code.
            desiredDuration - The desired duration of role assumption, in seconds.
                              This must be less than or equal to the role's allowed
                              maximum duration. It defaults to 3600, which is the
                              default duration for a new role. The maximum (per docs)
                              is 43200.
            durationRatio   - Optional: if passed, the assume-role operation will be
                              retried, with each subsequent duration being calculated
                              by multiplying the previous by this value (which must
                              be < 1), until the duration value is < 900 (the minimum
                              allowed).

        Returns the credentials extracted from the AssumeRole API.

        Also updates the global variable actualDuration, with the discovered duration.
    """
    global actualDuration
    request = {}
    request['RoleSessionName'] = generate_session_name()
    if re.fullmatch("arn:aws:iam::[0-9]*:role/.+", arnOrName):
        request['RoleArn'] = arnOrName
    else:
        request['RoleArn'] = lookup_role_arn(arnOrName)
    if mfaCode:
        userArn = sts_client.get_caller_identity()['Arn']
        mfaArn = userArn.replace(":user/", ":mfa/")
        request['SerialNumber'] = mfaArn
        request['TokenCode']    = mfaCode
    while True:
        try:
            request['DurationSeconds'] = desiredDuration
            response = sts_client.assume_role(**request);
            actualDuration = desiredDuration
            return response['Credentials']
        except ClientError as ex:
            if not durationRatio or str(ex).find('requested DurationSeconds exceeds') == -1:
                raise
            if desiredDuration <= 900:
                raise "exceeded allowed duration but requested duration is already at minimum"
            desiredDuration = max(900, int(desiredDuration * durationRatio))

def run_with_role(command, printDuration, arnOrName, mfaCode=None, desiredDuration=3600, durationRatio=None):
    """ Runs an arbitrary command after assuming a role.

        The "command" argument is an array that's passed to execvpe(); the first element
        of this array will be reported as the command name.

        The "printDuration" argument is a boolean that indicates whether to print the
        duration that the role will be assumed.

        All other arguments are per assume_role().
    """
    credentials = assume_role(arnOrName, mfaCode, desiredDuration, durationRatio)
    if printDuration:
        print(f'assumed role duration = {actualDuration} seconds ({actualDuration / 3600.0} hours)')
    new_env = os.environ
    new_env['AWS_ACCESS_KEY']        = credentials['AccessKeyId']
    new_env['AWS_ACCESS_KEY_ID']     = credentials['AccessKeyId']
    new_env['AWS_SECRET_KEY']        = credentials['SecretAccessKey']
    new_env['AWS_SECRET_ACCESS_KEY'] = credentials['SecretAccessKey']
    new_env['AWS_SESSION_TOKEN']     = credentials['SessionToken']
    os.execvpe(command[0], command, new_env)


if __name__ == "__main__":
    kwargs = { 'desiredDuration': 43200, 'durationRatio': 0.5 }
    if os.path.basename(__file__) == 'assume-role.py':
        if len(sys.argv) < 2 or len(sys.argv) > 3:
            print(__doc__)
            sys.exit(1)
        shell=os.environ.get('SHELL', '/bin/bash')
        if len(sys.argv) == 3:
            kwargs['mfaCode'] = sys.argv[2]
        run_with_role([shell], True, sys.argv[1], **kwargs)
    elif os.path.basename(__file__) == 'run-with-role.py':
        if len(sys.argv) < 2:
            print(__doc__)
            sys.exit(1)
        if re.match("^\d{6}$", sys.argv[2]):
            kwargs['mfaCode'] = sys.argv[2]
            command = sys.argv[3:]
        else:
            command = sys.argv[2:]
        run_with_role(command, False, sys.argv[1], **kwargs)
    else:
        print(__doc__)
        sys.exit(1)
