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
import os
import re
import sys


# arg_parser is a global so that we can write help text from multiple places
arg_parser = None


def parse_args(argv=None):
    """ Parses all arguments, defaulting to environment variables if present.
        """
    global arg_parser
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
    args = arg_parser.parse_args(argv or sys.argv)
    args.cluster = args.cluster or os.environ.get("ECS_CLUSTER")
    args.subnets = args.subnets or os.environ.get("ECS_SUBNETS")
    args.security_groups = args.security_groups or os.environ.get("ECS_SECURITY_GROUPS")
    return args


def exit_if_none(value, message):
    """ If the passed value is None, prints the specified message along with the
        program help text, and exits. If not None, returns the value.
        """
    if value is None:
        print(message)
        print()
        arg_parser.print_help()
        sys.exit(1)
    else:
        return value


def validate_cluster(cluster):
    """ Verifies that the named cluster exists.
        """
    if cluster is None:
        return None
    clusters = boto3.client('ecs').describe_clusters(clusters=["Default"])['clusters']
    if len(clusters) != 1:
        exit_if_none(None, f"invalid cluster: {cluster}")
    return clusters[0]['clusterArn']

def validate_subnets(subnet_spec):
    """ Splits the provided string and verifies that each subnet exists.
        """
    exit_if_none(subnet_spec, "Missing subnets")
    actual_subnets = {}
    paginator = boto3.client('ec2').get_paginator('describe_subnets')
    for page in paginator.paginate():
        for subnet in page['Subnets']:
            actual_subnets[subnet['SubnetId']] = subnet['VpcId']
    subnets = []
    vpcs = set()
    for subnet_id in subnet_spec.split(","):
        vpc_id = actual_subnets.get(subnet_id)
        exit_if_none(vpc_id, f"invalid subnet: {subnet_id}")
        subnets.append(subnet_id)
        vpcs.add(vpc_id)
    if (len(vpcs) > 1):
        exit_if_none(None, "subnets belong to different VPCs")
    return subnets


def validate_security_groups(sg_spec):
    """ Splits the provided string and verifies that each security group exists.
        """
    exit_if_none(sg_spec, "Missing security groups")
    actual_sgs = {}
    paginator = boto3.client('ec2').get_paginator('describe_security_groups')
    for page in paginator.paginate():
        for sg in page['SecurityGroups']:
            actual_sgs[sg['GroupId']] = sg.get('VpcId') # some people may still have non-VPC groups
    security_groups = []
    vpcs = set()
    for sg_id in sg_spec.split(","):
        vpc_id = actual_sgs.get(sg_id)
        exit_if_none(vpc_id, f"invalid security group: {sg_id}")
        security_groups.append(sg_id)
        vpcs.add(vpc_id)
    if (len(vpcs) > 1):
        exit_if_none(None, "security groups belong to different VPCs")
    return security_groups


def validate_task_definition(taskdef_name, version):
    """ Verifies that the task definition exists. If not given a version, just
        checks the name; otherwise both name and version must match. Returns
        the task definition ARN if valid.
        """
    exit_if_none(taskdef_name, "Missing task definition name")
    if version:
        taskdef_name = f"{taskdef_name}:{version}"
    # ECS throws if it can't find a task definition
    try:
        taskdef = boto3.client('ecs').describe_task_definition(taskDefinition=taskdef_name).get('taskDefinition')
        return taskdef['taskDefinitionArn']
    except:
        return exit_if_none(None, f"can't find task definition: {taskdef_name}")


def retrieve_container_names(taskdef_name):
    """ Retrieves the task definition and returns a list of the containers
        that it contains.
        """
    taskdef = boto3.client('ecs').describe_task_definition(taskDefinition=taskdef_name).get('taskDefinition')
    containers = []
    for container in taskdef['containerDefinitions']:
        containers.append(container['name'])
    return containers


def environment_overrides(container_names, envar_specs):
    """ Applies environment variable overrides to the passed list
        of containers. Returns a dict, keyed by container name,
        where each item in the dict has name-value pairs for the
        environment overrides that apply to that container.
        """
    matcher = re.compile(r"(([-\w]+):)*(\w+)=(.*)", re.ASCII)
    overrides_by_container = dict([[k,dict()] for k in container_names])
    for spec in envar_specs:
        match = matcher.match(spec)
        exit_if_none(match, f"invalid environment override: {spec}")
        container_name = match.group(2)
        env_name = match.group(3)
        env_value = match.group(4)
        if container_name:
            container_override = overrides_by_container.get(container_name)
            exit_if_none(container_override, f"invalid container for override: {container_name}")
            container_override[env_name] = env_value
        else:
            for container_override in overrides_by_container.values():
                container_override[env_name] = env_value
    return overrides_by_container


def construct_container_overrides(taskdef_name, envar_specs):
    container_names = retrieve_container_names(taskdef_name)
    env_overrides = environment_overrides(container_names, envar_specs)
    result = []
    for container_name in container_names:
        container_env = []
        for k,v in env_overrides.get(container_name, {}).items():
            container_env.append({
                "name": k,
                "value": v
            })
        result.append({
            "name": container_name,
            "environment": container_env
        })
    return result


if __name__ == "__main__":
    args = parse_args()
    args.cluster = validate_cluster(args.cluster)
    args.subnets = validate_subnets(args.subnets)
    args.security_groups = validate_security_groups(args.security_groups)
    args.taskdef = validate_task_definition(args.taskdef, args.taskdef_version)
