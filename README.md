Grab-bag of utilities and other stuff that I use with AWS. Easier to keep track of as a project rather than lots of gists.

## Lambdas

Directory                                                           | Contents
--------------------------------------------------------------------|----------
[cloudwatch-log-cleanup](lambda/cloudwatch-log-cleanup)             | Deletes CloudWatch log streams that are empty because of the log group's retention period.
[cloudwatch-logs-to-kinesis](lambda/cloudwatch-logs-to-kinesis)     | Destination for a CloudWatch Logs subscription that transforms messages to JSON and puts them on a Kinesis stream.
[elb-to-es](lambda/elb-to-es)                                       | Imports Elastic Load Balancer logfiles into Elasticsearch.
[es-cleanup-signed](lambda/es-cleanup-signed)                       | Cleans up old indexes from an Elasticsearch cluster. See [this](https://www.kdgregory.com/index.php?page=aws.loggingPipeline) for more info.
[es-cleanup-unsigned](lambda/es-cleanup-unsigned)                   | An Elasticsearch cleanup Lambda for clusters that allow unsigned access.


## Terraform

Directory                                                           | Contents
--------------------------------------------------------------------|----------
[users](terraform/users)                                            | Creates users, groups, and roles in a multi-account organization.


## Command-line utilities

Each is documented in its header, and exposes functions that may be useful for other programs.

Note: to run you must have `boto3` installed.

Program                                                             | Description
--------------------------------------------------------------------|----------
[cf-env.py](utils/cf-env.py)                                        | Populates environment variables from the parameters and outputs of a CloudFormation stack.
[assume-role.py](utils/assume-role.py)                              | Spawns a subshell with authentication credentials for a specified role.

In addition, I have a collection of command-line snippets [here](cli.md).
