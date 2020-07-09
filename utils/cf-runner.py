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

"""
Creates or updates a CloudFormation stack.

This script is optimized for the case where you're deploying multiple related
stacks. To that end, it retrieves saved configuration from a JSON file, and
writes stack outputs to that file after successful create/update. An example
use case is an infrastructure stack that outputs "VpcId", which is then
consumed by application stacks.

Invocation:

  cf-runner.py STACK_NAME TEMPLATE_PATH CONFIG_FILE [ NAME=VALUE [...] ]

Where:

  STACK_NAME    is the stack to be created or updated.
  TEMPLATE_PATH is the path to the CloudFormation template.
  CONFIG_FILE   is the path to a JSON file containing saved configuration.
  NAME          is the name of a template-specific parameter.
  VALUE         is the value for that parameter.
"""


import boto3
import json
import os.path
import sys
import time


class Config:
    """ Manages the saved configuration and overrides.

        Saved configuration is loaded when this object is constructed,
        but written explicitly.

        There are two types of overrides: the first, "cli_params" is a
        list of "NAME=VALUE" strings, assumed to be from a command-line
        invocation. The second, "overrides", is a dict, assumed to be
        built by the program. Of these, "cli_params" takes precedence,
        with the default parameter file being lowest on the chain.

        Overrides are not written to the configuration file; they are
        valid for only the current instance.
    """

    def __init__(self, saved_config_path, cli_params=[], overrides={}):
        self.saved_config_path = saved_config_path
        self.saved_config = {}
        if os.path.exists(self.saved_config_path):
            with open(self.saved_config_path) as f:
                self.saved_config = json.load(f)
        self.cli_params = {}
        for arg in cli_params:
            kv = arg.split('=')
            self.cli_params[kv[0]] = kv[1]
        self.overrides = overrides

    def get(self, name, default=None):
        """ Returns the value of a parameter, applying overrides.
        """
        return self.cli_params.get(name,
                    self.overrides.get(name,
                         self.saved_config.get(name, default)))

    def update_and_save(self, new_params, path=None):
        """ Updates the default parameter file and saves it. This is called by the
            stack-builder when it extracts stack outputs.

            If provided with a path, writes the default parameter file to that path.
            Otherwise overwrites the original default parameter file.
        """
        self.saved_config.update(new_params)
        if not path:
            path = self.saved_config_path
        with open(path, "w") as f:
            json.dump(self.saved_config, f)


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

    def apply(self, stack_name, saved_config):
        stack = Stack(self.client, stack_name, self, saved_config)
        stack.create_or_update()
        return stack


class Stack:
    """ Creates or updates a stack, and holds information about it.
    """

    def __init__(self, client, stack_name, template, config):
        self.client = client
        self.stack_name = stack_name
        self.template = template
        self.config = config
        self.existing_params = {}

    def create_or_update(self):
        self._retrieve_stack_info()
        self._build_parameter_list()
        if self.stack_id:
            self._update_stack()
        else:
            self._create_stack()
        self._wait_until_done()
        self._extract_outputs()

    def _retrieve_stack_info(self):
        paginator = client.get_paginator('describe_stacks')
        for page in paginator.paginate():
            for stack in page['Stacks']:
                if stack['StackName'] == self.stack_name:
                    self.stack_id = stack['StackId']
                    for param in stack['Parameters']:
                        k = param['ParameterKey']
                        v = param['ParameterValue']
                        self.existing_params[k] = v
                    return
        self.stack_id = None
        
    def _build_parameter_list(self):
        self.params_to_apply = []
        for name in template.param_names:
            value = self.config.get(name,
                        self.existing_params.get(name))
            if value:
                self.params_to_apply.append({
                    'ParameterKey': name,
                    'ParameterValue': value
                })

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


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    client = boto3.client('cloudformation')
    config = Config(sys.argv[3], sys.argv[4:])
    template = Template(client, sys.argv[2])
    stack = template.apply(sys.argv[1], config)
    config.update_and_save(stack.outputs)
