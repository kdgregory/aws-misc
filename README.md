Grab-bag of utilities and other stuff that I use with AWS. Easier to keep track of as a project rather than lots of gists.


## Command-line utilities (Python)

Each is documented in its header, and exposes functions that may be useful for other programs.

To run you must have `boto3` installed.

Program                                                 | Description
--------------------------------------------------------|----------
[assume-role.py](utils/assume-role.py)                  | Spawns a subshell with authentication credentials for a specified role.
[cf-env.py](utils/cf-env.py)                            | Populates environment variables from the parameters and outputs of a CloudFormation stack.
[cf-runner.py](utils/cf-runner.py)                      | Creates/updates CloudFormation scripts, using an external store of common parameters
[kinesis_reader.py](utils/kinesis_reader.py)            | Reads from a Kinesis stream, writing output as JSON.
[logs_reader.py](utils/logs_reader.py)                  | Reads from a CloudWatch Logs log group/stream, writing output as JSON.
[sm-env.py](utils/sm-env.py)                            | Populates environment variables from a Secrets Manager secret.


## Snippets

Isolated pieces of code or configuration, intended to be pasted elsewhere.

* [AWS CLI](snippets/cli.md)
* [IAM Roles/Policies](snippets/iam.md)
* [Python functions](snippets/python.md)
* [Redshift queries](snippets/redshift.md)


## Lambda

Complete Lambda implementations and code intended to be used with Lambdas. Mostly in Python.

Directory                                                           | Contents
--------------------------------------------------------------------|----------
[cloudwatch-log-cleanup](lambda/cloudwatch-log-cleanup)             | Deletes CloudWatch log streams that are empty because of the log group's retention period.
[cloudwatch-log-transform](lambda/cloudwatch-log-transform)         | Transforms CloudWatch Logs events from a Kinesis stream.
[elb-to-es](lambda/elb-to-es)                                       | Imports Elastic Load Balancer logfiles into Elasticsearch.
[es-index-cleanup](lambda/es-index-cleanup)                         | Deletes up old indexes from an Elasticsearch cluster. See [this blog post](https://www.kdgregory.com/index.php?page=aws.loggingPipeline) for more info.
[json-logging](lambda/json-logging)                                 | A module that will configure the Python logging framework for JSON output with Lambda-specific metadata.


## Terraform

Directory                                                                   | Contents
----------------------------------------------------------------------------|----------
[modules/lambda](terraform/modules/lambda)                                  | Module for creating Lambda functions.
[modules/sqs](terraform/modules/sqs)                                        | Module for creating SQS queues.
[modules/s3_deployment](terraform/modules/s3_deployment)                    | Module for maintaining Lambda deployment bundles on S3.
[examples/provision-via-bastion](terraform/examples/provision-via-bastion)  | Example of provisioning an instance via a bastion host.
[templates](terraform/templates)                                            | Templates for common config files.
