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
import logging
import re

from botocore.exceptions import ClientError

logger = logging.getLogger("aws_util.create_client")
logger.setLevel(logging.DEBUG)


def create_client(service, *, region_name=None, account=None, role_name=None, role_arn=None, session_name=None, policy=None, duration=None, log_actions=False):
    """ Creates a boto3 client object, optionally assuming a role to do so.

        Unrecoverable exceptions (typically, missing permissions) are allowed to
        propagate back to caller. Incorrect arguments raise ValueError, with a
        description of what's wrong.

        service         - Name of the service, as you would pass to boto3.client()
        region_name     - Name of the region for this client's services.
        account         - Used with `role_name` to identify an assumed role. If omitted,
                          uses the current (invoking) account.
        role_name       - The name of a role to assume.
        role_arn        - The ARN of a role to assume. If specified, do not specify account
                          or role_name.
        session_name    - A session name for the role. If omitted, and the client is being
                          created with long-term user credentials, then this function will
                          combine the invoker's account and username. If invoked from an
                          existing assumed role session, will use the name from that session.
        policy          - An optional IAM policy, used to restrict the permissions of the
                          assumed role. Requires either account/role_name or role_arn.
        duration        - The duration, in seconds, of the role session. If this exceeds the
                          maximum duration for the role, then this function will attempt a
                          shorter duration, cutting the value in half for each attempt. If
                          omitted, this function will use the defined maximum duration for
                          roles specified by name, or a default of 8 hours (which may be
                          reduced as described previously).
        log_actions     - If True, then this function will log everything that it tries to
                          do (at debug level).
        """
    if account and not role_name:
        raise ValueError("create_client: account requires role_name")
    if policy and not (role_name or role_arn):
        raise ValueError("create_client: policy requires role")
    if account and role_name and role_arn:
        raise ValueError("create_client: can not specify both account/role_name and role_arn")

    if not role_name and not role_arn:
        return _create_basic_client(service, region_name, log_actions)

    sts_client = boto3.client("sts")
    iam_client = boto3.client("iam")

    if account and role_name:
        role_arn = f"arn:aws:iam::{account}:role/{role_name}"
    elif role_name:
        role = _lookup_role(iam_client, role_name, log_actions)
        role_arn = role['Arn']
        if not duration:
            duration = role['MaxSessionDuration']

    if not duration:
        duration = 8 * 3600

    if not session_name:
        session_name = _construct_session_name(sts_client, log_actions)

    return _create_assumed_role_client(sts_client, service, region_name, role_arn, session_name, policy, duration, log_actions)


def _create_basic_client(service, region_name, log_actions):
    if log_actions:
        logger.debug(f"creating {service} client with default credentials")

    client_args = {}
    if region_name:
        client_args['region_name'] = region_name
    return boto3.client(service, **client_args)


def _create_assumed_role_client(sts_client, service, region_name, role_arn, session_name, policy, duration, log_actions):
    if log_actions:
        logger.debug(f"creating {service} client with assumed role {role_arn}; session name: {session_name}, duration: {duration}, policy: {policy}")

    role_args = {
        'RoleArn': role_arn,
        'RoleSessionName': session_name,
    }
    if policy:
        role_args['Policy'] = policy

    while True:
        try:
            role_args['DurationSeconds'] = duration
            credentials = sts_client.assume_role(**role_args)['Credentials']
            client_args = {
                'aws_access_key_id': credentials['AccessKeyId'],
                'aws_secret_access_key': credentials['SecretAccessKey'],
                'aws_session_token': credentials['SessionToken']
            }
            if region_name:
                client_args['region_name'] = region_name
            return boto3.client(service, **client_args)
        except ClientError as ex:
            if duration == 900:
                raise Exception("unable to assume role with minimum allowed duration (shouldn't happen)")
            if not "MaxSessionDuration" in str(ex):
                raise
            if duration >= 1800:
                duration /= 2
            else:
                duration = 900


def _lookup_role(iam_client, role_name, log_actions):
    # this will throw if the role doesn't exist; we can't unit-test that because the
    # exception, botocore.errorfactory.NoSuchEntityException, is generated at runtime
    if log_actions:
        logger.debug(f"retrieving role {role_name} for invoking account")
    resp = iam_client.get_role(RoleName=role_name)
    return resp['Role']


def _construct_session_name(sts_client, log_actions):
    if log_actions:
        logger.debug("generating session name from caller identity")
    identity = sts_client.get_caller_identity()
    resource_id = identity['Arn'].rpartition("/")[2] or "unknown"
    if identity['UserId'].startswith("AIDA"):
        return f"{identity['Account']}-{resource_id}"
    else:
        return resource_id



    user_match = re.match(r"arn:[^:]*:iam::(\d+):user/(.*)$", identity['Arn'])
    if user_match:
        return f"{user_match.group(1)}-{user_match.group(2)}"
    assumed_role_match = re.match(r"arn:[^:]*:sts::(\d+):assumed-role/[^/]+/(.*)$", identity['Arn'])
    if assumed_role_match:
        return assumed_role_match.group(2)
    else:
        return "unknown"
