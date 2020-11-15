Grab-bag of utilities and other stuff that I use with AWS. Easier to keep track of as a project rather than lots of gists.

## Lambdas

Directory                                                           | Contents
--------------------------------------------------------------------|----------
[cloudwatch-log-cleanup](lambda/cloudwatch-log-cleanup)             | Deletes CloudWatch log streams that are empty because of the log group's retention period.
[cloudwatch-log-transform](lambda/cloudwatch-log-transform)         | Transforms CloudWatch Logs events from a Kinesis stream.
[elb-to-es](lambda/elb-to-es)                                       | Imports Elastic Load Balancer logfiles into Elasticsearch.
[es-cleanup-signed](lambda/es-cleanup-signed)                       | Cleans up old indexes from an Elasticsearch cluster. See [this](https://www.kdgregory.com/index.php?page=aws.loggingPipeline) for more info.
[es-cleanup-unsigned](lambda/es-cleanup-unsigned)                   | An Elasticsearch cleanup Lambda for clusters that allow unsigned access.
[json-logging](lambda/json-logging)                                 | A module that will configure the Python logging framework for JSON output with Lambda-specific metadata.


## Terraform

Directory                                                           | Contents
--------------------------------------------------------------------|----------
[provision-via-bastion](terraform/provision-via-bastion)            | Example of provisioning an instance via a bastion host.
[users-and-groups](terraform/users-and-groups)                      | Example of table-driven generation of users, groups, and group permissions.


## Command-line utilities

Each is documented in its header, and exposes functions that may be useful for other programs.

Note: to run you must have `boto3` installed.

Program                                                             | Description
--------------------------------------------------------------------|----------
[cf-env.py](utils/cf-env.py)                                        | Populates environment variables from the parameters and outputs of a CloudFormation stack.
[cf-runner.py](utils/cf-runner.py)                                  | Creates/updates CloudFormation scripts, using an external store of common parameters
[assume-role.py](utils/assume-role.py)                              | Spawns a subshell with authentication credentials for a specified role.


## Snippets

Isolated pieces of code or configuration, intended to be pasted elsewhere.

* [AWS CLI](snippets/cli.md)
* [IAM Roles/Policies](snippets/iam.md)
* [Python functions](snippets/python.md)
* [Redshift queries](snippets/redshift.md)
