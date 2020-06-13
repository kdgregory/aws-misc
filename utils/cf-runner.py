#!/usr/bin/env python3
################################################################################
# Copyright 2020 Keith D Gregory
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
# Creates or updates a CloudFormation stack.
#
# This script will retrieve parameter values from a provided parameter store,
# update that parameter store with any outputs from the stack, and wait for
# the stack to be successfully created.
#
# Invocation:
#
#   cf-runner.py TEMPLATE_PATH STACK_NAME PARAMS_PATH [ NAME=VALUE [...] ]
#
# Where:
#
#   TEMPLATE_PATH is the path to the CloudFormation template.
#   STACK_NAME    is the stack to be created or updated.
#   PARAMS_PATH   is the path to a JSON file containing the parameter store.
#   NAME          is the name of a template-specific parameter.
#   VALUE         is the value for that parameter.
#
################################################################################

import boto3
import json
import os.path
import sys
import time


class Params:
    """ Manages the parameter store and overrides.

        The parameter store is loaded from / written to a file, and is
        used to provide cross-stack configuration.

        There are two types of overrides: the first, "cli_params" is a
        list of "NAME=VALUE" strings, assumed to be from a command-line
        invocation. The second, "overrides", is a dict, assumed to be
        built by the program. Of these, "cli_params" takes precedence,
        with the parameter store being lowest on the chain.

        These overrides are not written to the parameter store; they are
        valid for only the current instance.
    """

    def __init__(self, param_store_path, cli_params=[], overrides={}):
        self.param_store_path = param_store_path
        self.param_store = {}
        if os.path.exists(self.param_store_path):
            with open(self.param_store_path) as f:
                self.param_store = json.load(f)
        self.cli_params = {}
        for arg in cli_params:
            kv = arg.split('=')
            self.cli_params[kv[0]] = kv[1]
        self.overrides = overrides

    def get(self,name):
        """ Returns the value of a parameter, applying overrides (CLI first,
            then dictory).
        """
        return self.cli_params.get(name,
                    self.overrides.get(name,
                         self.param_store.get(name)))

    def update(self, new_params):
        """ Updates the parameter store with the supplied dict, without writing
            the changes to disk.
        """
        self.param_store.update(new_params)

    def update_and_save(self, new_params, path=None):
        """ Updates the parameter store and saves it.

            If provided with a path, writes the parameter store to that path.
            Otherwise overwrites the original parameter store.
        """
        self.update(new_params)
        if not path:
            path = self.param_store_path
        with open(path, "w") as f:
            json.dump(self.param_store, f)


class Stack:
    """ Provides the ability to create or update a stack, and holds information
        about the stack after it has been created/updated.
    """

    def __init__(self, client, stack_name, template, param_store):
        self.client = client
        self.stack_name = stack_name
        self.template = template
        self.params = param_store

    def create_or_update(self):
        self._build_parameter_list()
        self._retrieve_stack_id()
        if self.stack_id:
            self._update_stack()
        else:
            self._create_stack()
        self._wait_until_done()
        self._extract_outputs()

    def _build_parameter_list(self):
        self.params_to_apply = []
        for name in template.param_names:
            value = self.params.get(name)
            if value:
                self.params_to_apply.append({
                    'ParameterKey': name,
                    'ParameterValue': value
                })

    def _retrieve_stack_id(self):
        paginator = client.get_paginator('describe_stacks')
        for page in paginator.paginate():
            for stack in page['Stacks']:
                if stack['StackName'] == self.stack_name:
                    self.stack_id = stack['StackId']
                    return
        self.stack_id = None

    def _create_stack(self):
        print("creating new stack")
        response = client.create_stack(
            StackName=self.stack_name,
            TemplateBody=template.template_body,
            Parameters=self.params_to_apply,
            TimeoutInMinutes=30,
            Capabilities=template.capabilities_needed,
            OnFailure='DO_NOTHING'
            )
        self.stack_id = response['StackId']
        print(f"stack id: {self.stack_id}")

    def _update_stack(self):
        print(f"updating existing stack: {self.stack_id}")
        response = client.update_stack(
            StackName=self.stack_id,
            TemplateBody=template.template_body,
            Parameters=self.params_to_apply,
            Capabilities=template.capabilities_needed
            )

    def _wait_until_done(self):
        for x in range(0, 15 * 4 * 30):
            print(f"waiting for stack to build ({x * 15} seconds)")
            desc = self.client.describe_stacks(StackName=self.stack_id)
            self.status = desc['Stacks'][0]['StackStatus']
            if self.status.endswith("COMPLETE"):
                return
            time.sleep(15)
        print(f"timeout with status {self.stau}")

    def _extract_outputs(self):
        self.outputs = {}
        desc = client.describe_stacks(StackName=self.stack_id)
        for output in desc['Stacks'][0].get('Outputs', []):
            self.outputs[output['OutputKey']] = output['OutputValue']


class Template:
    """ Manages information extracted from a CloudFormation template, and allows
        the application of that template to create a stack.

        By default the template is loaded and validated at construction-time. This
        will populate the exposed instance variables. For testing, you can defer
        loading until a later time.
    """

    def __init__(self, client, path, eager_load=True):
        self.client = client
        self.template_path = path
        self.param_names = set()
        self.default_values = {}
        if eager_load:
            self.load()

    def load(self):
        """ Loads and validates the template.
        """
        with open(self.template_path) as f:
            self.template_body = f.read()
        response = client.validate_template(TemplateBody=self.template_body)
        self.capabilities_needed = response.get('Capabilities', [])
        for param in response.get('Parameters', []):
            param_name = param['ParameterKey']
            self.param_names.add(param_name)
            default_value = param.get('DefaultValue')
            if default_value:
                self.default_values[param_name] = default_value

    def apply(self, stack_name, param_store):
        stack = Stack(self.client, stack_name, self, param_store)
        stack.create_or_update()
        return stack


if __name__ == "__main__":
    client = boto3.client('cloudformation')
    params = Params(sys.argv[3], sys.argv[4:])
    template = Template(client, sys.argv[1])
    stack = template.apply(sys.argv[2], params)
    params.update_and_save(stack.outputs)
