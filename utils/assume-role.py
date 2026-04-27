#!/usr/bin/env python3
################################################################################
# Copyright 2019-2025 Keith D Gregory
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
Assumes a role and either starts a new shell or runs an arbitrary command using
that role. 

Invocation:

    assume-role.py [OPTIONS] ROLE_OR_ACCOUNT
    run-with-role.py [OPTIONS] ROLE_OR_ACCOUNT COMMAND

Caveats:

    Only supports virtual MFA devices (this is because hardware devices are
    identified differently).

    For assume-role, if you load your AWS credentials in .bashrc, they'll
    overwrite the assumed-role credentials. Don't do that.
"""

import argparse
import boto3
import json
import os
import re
import sys

from botocore.exceptions import ClientError


DEFAULT_DURATION = 8 * 3600
ORG_ROLE = "OrganizationAccountAccessRole"

arg_parser = None
iam_client = boto3.client('iam')
sts_client = boto3.client('sts')

# this variable is a hack that lets us report the role duration from CLI invocation
actualDuration = None


def parse_args(prog, is_run_with, argv):
    global arg_parser
    arg_parser = argparse.ArgumentParser(prog=prog)
    arg_parser.add_argument("--org",
                            action="store_const",
                            const=True,
                            default=False,
                            dest="assume_org_role",
                            help=f"Assumes {ORG_ROLE} in the AWS account specified by ROLE_OR_ACCOUNT.")
    arg_parser.add_argument("--mfa",
                            metavar="MFA_CODE",
                            dest="mfa_code",
                            help="An MFA code, for roles that require one.")
    arg_parser.add_argument("-d", "--duration",
                            metavar="DURATION",
                            dest="duration",
                            type=int,
                            help="""Duration (in seconds) that the role will be valid. If this exceeds the
                                    allowed duration of the role, the program will repeatedly attempt to
                                    assume the role, halving the duration each time.

                                    If not specified, the default duration is 28800 (8 hours).
                                    """)
    arg_parser.add_argument("--region",
                            metavar="REGION",
                            dest="region",
                            help="""If used, indicates that the region should be configured (using standard
                                    AWS environment variables) for the invoked command/shell.
                                    """)
    arg_parser.add_argument("role",
                            metavar="ROLE_OR_ACCOUNT",
                            help="""The name or ARN of the role to assume, unless --org is specified, in
                                    which case it's the 12-digit account ID of the target account.
                                    """)
    if is_run_with:
        arg_parser.add_argument("command",
                                metavar="COMMAND",
                                nargs="+",
                                help="""The command to invoke with using this role. This command is invoked
                                        with exec(2), and has whatever environment your current process has,
                                        along with AWS-specific variables for credentials.
                                        """)
    args = arg_parser.parse_args(argv)
    if args.assume_org_role:
        if not re.match(r"\d{12}$", args.role):
           invocation_error("invalid account ID")
        args.role = f"arn:aws:iam::{args.role}:role/{ORG_ROLE}"
    if not args.duration:
        args.duration = DEFAULT_DURATION
    return args


def invocation_error(message):
    print(f"invocation error: {message}", file=sys.stderr)
    print(file=sys.stderr)
    arg_parser.print_help(file=sys.stderr)
    sys.exit(1)


def lookup_role_arn(role_name):
    """ Returns the ARN for a role with the given name, None if it doesn't exist.

        The name should include any path (eg: "/service-role/Foo", but it will be
        matched even if the path is omitted (although you may get the wrong role).
    """
    lastSlash = role_name.rfind("/")
    if lastSlash >= 0:
        prefix = role_name[:lastSlash+1]
        baseName = role_name[lastSlash+1:]
    else:
        prefix = "/"
        baseName = role_name
    for page in iam_client.get_paginator('list_roles').paginate(PathPrefix=prefix):
        for role in page['Roles']:
            if baseName == role['RoleName']:
                return role['Arn']
    raise Exception(f'Unable to find role with name "{role_name}"')


def generate_session_name():
    """ Creates a session name based on invoking user identity. Preference is given
        to actual account/username, with fallback to existing session identity for
        an assumed role, with account ID as ultimate fallback (which I don't think
        will ever happen).
    """
    invoker = sts_client.get_caller_identity()
    user_match = re.fullmatch(r"arn:aws:iam::[0-9]+:user/(.*)", invoker['Arn'])
    if user_match:
        return str(invoker['Account']) + "-"  + user_match.group(1)
    role_match = re.fullmatch(r"arn:aws:sts::[0-9]+:assumed-role/.*/(.*)", invoker['Arn'])
    if role_match:
        return role_match.group(1)
    return str(invoker['Account'])


def assume_role(arn_or_name, duration, mfa_code=None):
    """ Assumes a role and returns its credentials.

        Arguments:
            arn_or_name     - May be passed either a role name in the current account
                              (in which case the ARN is retrieved) or an ARN (which
                              may belong to the current account or another account).
            duration        - The number of seconds for the session duration. If unable
                              to assume the role for this duration, we will try again
                              with half that value (but no less than 900 seconds).
            mfa_code        - Optional: if present, the user's virtual MFA device is
                              retrieved and passed to the request with this code.

        Returns the credentials extracted from the AssumeRole API.

        Also updates the global variable actualDuration, with the discovered duration.
    """
    global actualDuration
    if duration < 900:
        raise Exception(f"invalid duration ({duration}; must be at least 900 seconds")
    request = {}
    request['RoleSessionName'] = generate_session_name()
    if re.fullmatch("arn:aws:iam::[0-9]*:role/.+", arn_or_name):
        request['RoleArn'] = arn_or_name
    else:
        request['RoleArn'] = lookup_role_arn(arn_or_name)
    if mfa_code:
        userArn = sts_client.get_caller_identity()['Arn']
        mfaArn = userArn.replace(":user/", ":mfa/")
        request['SerialNumber'] = mfaArn
        request['TokenCode']    = mfa_code
    try:
        request['DurationSeconds'] = duration
        response = sts_client.assume_role(**request);
        actualDuration = duration
        return response['Credentials']
    except ClientError as ex:
        # it would be nice if the SDK reported duration errors with a different exception
        if str(ex).find('requested DurationSeconds exceeds') >= 0:
            return assume_role(arn_or_name, int(duration / 2), mfa_code=None)
        else:
            raise


def run_with_role(command, print_duration, args):
    """ Runs an arbitrary command after assuming a role.

        command         - the command to run
        print_duration  - if True, prints the duration of the session
        args            - parsed command-line args

        Note: depending on the SDK there are multiple possible access/secret key envars. We try
        to cover everything here.
    """
    credentials = assume_role(args.role, args.duration, args.mfa_code)
    if print_duration:
        print(f'assumed role duration = {actualDuration} seconds ({actualDuration / 3600.0} hours)')
    new_env = os.environ
    new_env['AWS_ACCESS_KEY_ID']      = credentials['AccessKeyId']
    new_env['AWS_SECRET_ACCESS_KEY']  = credentials['SecretAccessKey']
    new_env['AWS_ACCESS_KEY']         = credentials['AccessKeyId']
    new_env['AWS_SECRET_KEY']         = credentials['SecretAccessKey']
    new_env['AWS_SESSION_TOKEN']      = credentials['SessionToken']
    if args.region:
        new_env['AWS_REGION']         = args.region
        new_env['AWS_DEFAULT_REGION'] = args.region

    os.execvpe(command[0], command, new_env)


if __name__ == "__main__":
    prog = sys.argv[0]
    is_run_with = prog.find("run-with-role") >= 0
    args = parse_args(prog, is_run_with, sys.argv[1:])
    if is_run_with:
        run_with_role(args.command, False, args)
    else:
        shell=os.environ.get('SHELL', '/bin/bash')
        run_with_role([shell], True, args)
