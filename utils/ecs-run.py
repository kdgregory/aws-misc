#!/usr/bin/env python3
################################################################################
# Copyright Keith D Gregory
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


import argparse
import boto3
import json
import os.path
import sys
import time


def parse_args():
    arg_parser = argparse.ArgumentParser(description="Runs an ECS task")
    arg_parser.add_argument("--cluster", dest='cluster',
                            help="""Cluster where the task will be run; default cluster if not specified
                                 Defaults to value of ECS_CLUSTER environment variable.""")
    arg_parser.add_argument("--subnets", dest='subnets', metavar="COMMA_SEPARATED_LIST",
                           help="""One or more subnets where the task may run; must belong
                                to the VPC associated with the cluster.
                                Defaults to value of ECS_SUBNETS environment variable.""")
    arg_parser.add_argument("--security_groups", "--sg", dest='security_groups', metavar="COMMA_SEPARATED_LIST",
                           help="""Up to five security group IDs that will be associated with task.
                                Defaults to value of ECS_SECURITY_GROUPS environment variable.""")
    arg_parser.add_argument("--task_definition_version", dest='taskdef_version', metavar="VERSION",
                           help="The version of the task definition; defaults to the latest version.")
    arg_parser.add_argument('taskdef', metavar="TASK_DEFINITION_NAME",
                            help="The name of the task definition")
    arg_parser.add_argument('envars', nargs='*', metavar="ENVIRONMENT_OVERRIDE",
                            help="""Environment variable overrides for the task. 
                                 May be specified as KEY=VALUE for a single-container task;
                                 must be specified as CONTAINER:KEY=VALUE if task has multiple
                                 containers.""")

    args = arg_parser.parse_args()

    args.cluster = args.cluster or os.environ.get("ECS_CLUSTER")
    args.subnets = args.subnets or os.environ.get("ECS_SUBNETS")
    args.security_groups = args.security_groups or os.environ.get("ECS_SECURITY_GROUPS")

    # TODO: validate subnets and security groups
    return args


if __name__ == "__main__":
    args = parse_args()
    print(f"ready to go: {args}")
