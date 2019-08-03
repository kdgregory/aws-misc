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
#
# Starts a new shell with environment variables for an assumed role.
#
# Invocation:
#
#   assume-role.py ROLE_NAME | ROLE_ARN
#
# Where:
#
#   ROLE_NAME   is the simple name (including path) of an assumable role in
#               the current account.
#   ROLE_ARN    is the ARN of an assumable role from any account.
#
# Caveats:
#
#   You can't load credentials in your .bashrc, or they will overwrite the
#   assumed-role credentials.
#
# Programmatic use:
#
#   lookupRoleArn(roleName) - Retrieves the ARN corresponding to a simple name
#   generateSessionName()   - Generates a UUID-based session ID that includes
#                             the user's account and username if available.
#   assumeRole(nameOrArn)   - Returns credentials for an assumed role, specified
#                             either by name or ARN.
#
################################################################################

import boto3
import json
import os
import re
import sys
import uuid

iamClient = boto3.client('iam')
stsClient = boto3.client('sts')


def lookupRoleArn(roleName):
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
    for page in iamClient.get_paginator('list_roles').paginate(PathPrefix=prefix):
        for role in page['Roles']:
            if baseName == role['RoleName']:
                return role['Arn']
    raise Exception(f'Unable to find role with name "{roleName}"')


def generateSessionName():
    """ Creates a session name based based on the account and name of the invoking
        user (if known) and a UUID.
    """
    invokerArn = stsClient.get_caller_identity()['Arn']
    matched = re.fullmatch(r"arn:aws:iam::([0-9]+):user/(.*)", invokerArn)
    if matched:
        return matched.group(1) + "-" + matched.group(2) + "-" + str(uuid.uuid4())
    else:
        return str(uuid.uuid4())



def assumeRole(arnOrName):
    """ Assumes a role and returns its credentials.

        May be passed either a role name (in which case the ARN is retrieved) or an
        ARN (in which case it's used as-is).
    """
    if re.fullmatch("arn:aws:iam::[0-9]*:role/.+", arnOrName):
        roleArn = arnOrName
    else:
        roleArn = lookupRoleArn(arnOrName)
    return stsClient.assume_role(
        RoleArn=roleArn,
        RoleSessionName=generateSessionName()
        )['Credentials']


if __name__ == "__main__":
    credentials = assumeRole(sys.argv[1])
    shell=os.environ.get('SHELL', '/bin/bash')
    new_env = os.environ
    new_env['AWS_ACCESS_KEY']        = credentials['AccessKeyId']
    new_env['AWS_ACCESS_KEY_ID']     = credentials['AccessKeyId']
    new_env['AWS_SECRET_KEY']        = credentials['SecretAccessKey']
    new_env['AWS_SECRET_ACCESS_KEY'] = credentials['SecretAccessKey']
    new_env['AWS_SESSION_TOKEN']     = credentials['SessionToken']
    os.execvpe(shell, [shell], new_env)
