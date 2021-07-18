Creates a Lambda and related resources:

* The Lambda's execution role, which my default allows basic execution privileges.
* A CloudWatch log group, following the standard Lamba naming convention.
* For VPC deployments, a ["marker"](#marker_security_group) security group.


## Configuration

There are lots of variables, and many have defaults. While most are obvious, and tie
directly to the [aws_lambda_function](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_function)
arguments, some have peculiarities described below.

A note on default values: some variables have meaningful defaults, some have "null"
as the default, and some have "none". Those with null will be ignored if you do not
provide a default; for example, `tags`. Those with none must be specified in your
configuration.

* `name`

  The name of the Lambda. Also used as the name of the Lambda's marker security group,
  and as the base for its execution role (combined with the deployment region).

  Default: none; you must specify this.

* `description`

  The Lambda's description.

  Default: a snarky message telling you to give it a real description.

* `runtime`

  The Lambda's runtime environment. See [AWS docs](https://docs.aws.amazon.com/lambda/latest/dg/API_CreateFunction.html#SSS-CreateFunction-request-Runtime)
  for currently supported runtimes.

* `filename`

  The name of a local file containing the Lambda's deployment bundle.

  Used only for local deployments; you must either provide this or `s3_bucket` and `s3_key`.

  Default: null.

* `s3_bucket`

  The name of a bucket containing the Lambda's deployment bundle.

  If you specify this, you must also specify `s3_key`, and may not specify `filename`.

  Default: null.

* `s3_key`

  The key used to retrieve the Lambda's deployment bundle from the bucket specified by `s3_bucket`.

  If you specify this, you must also specify `s3_bucket`, and may not specify `filename`.

  Default: null.

* `s3_version`

  The version identifier of a Lambda deployment bundle stored on S3. You don't need to use
  this to deploy from S3, unless you also upload the bundle via Terraform and want the Lambda
  to see the update. See the [s3_deployment](../s3_deployment) module for an example.

  Default: null

* `source_code_hash`

  A Base64-encoded SHA256 hash that determines whether the Lambda source code should be updated.

  This will be calculated if you specify `filename` and do not provide an overriding value. It
  is exposed for S3-based deployments (although there's no way to get the value from S3), or to
  _prevent_ a deployment that would otherwise occur (you'd have to preserve the value somehow).

  Default: null / value calculated from `filename`

* `handler`

  The fully-qualified name of the Lambda's handler function, The format of this value depends on
  the language you use to implement your function.

  Default: none.

* `memory_size`

  The amount of memory, in MB, to allocate to the function. Note that this also controls the
  amount of CPU that the function can use.

  Default: 1024 (which provides slightly more than 1/2 of a virtual CPU)

* `timeout`

  The number of seconds that the Lambda is allowed to run before being terminated.

  Default: 60

* `vpc_id`

  For VPC deployments, identifies the VPC where the Lambda will be deployed. If used, you
  must also specify `subnet_ids`.

  Default: null (Lambda is deployed outside VPC)

* `subnet_ids`

  For VPC deployments, identifies the subnets where the Lambda will be deployed. If used,
  you must also specify `vpc_id`, and the subnets must be within the VPC.

  You can specify "public" subnets, but the Lambda will not be assigned a public IP address.
  To access the Internet, you must deploy into a subnet that has a NAT; to access AWS
  services, VPC endpoints may be sufficient.

  Default: null (Lambda is deployed outside VPC)

* `security_group_ids`

  A list of up to 4 security groups to be be associated with the Lambda. This is only
  valid for deployment inside a VPC. These security groups are in addition to the
  marker group created by this module.

  Default: null

* `layers`

  A list of up to 5 ARNs, identifying Lambda layers that are to be part of the deployment.

  Default: null

* `env`

  A map of name-value pairs to be associated with the Lambda as environment variables.

  Default: null

* `tags`

  A map of name-value pairs that will be associated with the Lambda and all other
  resources created by this script as tags. See below for special handling of the
  [marker security group](#marker_security_group).

  Default: null

* `log_retention`

  The number of days that the CloudWatch log group associated with this Lambda will
  retain messages. If not specified, messages are retained indefinitely. If specified,
  the value must be in an allowed set of values, [as defined by the API](https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_PutRetentionPolicy.html#CWL-PutRetentionPolicy-request-retentionInDays).

  Default: null


## Outputs

This module provides the following outputs, for use by consuming modules. All outputs
refer to the created resource, so you can access all attributes of the resource (not
just its name or ARN).

* `lambda`

  The Lambda itself.

* `execution_role`

  The Lambda's execution role. In almost all cases, you will only care about the
  role's `name` property.

* `security_group`

  For VPC deployments only, the marker security group. For non-VPC deployments, this
  output is null.


## Examples

In all of the examples below, update `COMMIT` to an appropriate hash. Do not use `trunk`
unless you're OK with deployment configs that may change outside of your control.


### Build deployment bundle on local filesystem

This example uses the `archive` provider to create the deployment bundle from a local
directory; it's appropriate for simple Python or Node implementations. If you use Java
or other compiled languages, or require third-party libraries, you should build the
deployment bundle outside of Terraform (and should consider deploying via S3).

```
locals {
  lambda_name = "example"
}


data "archive_file" "example_lambda" {
  type        = "zip"
  output_path = "${path.module}/${local.lambda_name}.zip"
  source_dir  = "${path.module}/src"
  excludes    = [ "__pycache__" ]
}


module "example_lambda" {
  source = "github.com/kdgregory/aws-misc.git//terraform/modules/lambda?ref=COMMIT"

  name        = local.lambda_name
  description = "An example Lambda uploaded by Terraform config"

  handler     = "lambda_handler.handler"
  runtime     = "python3.8"
  filename    = data.archive_file.example_lambda.output_path
}
```


### Deployment bundle stored in S3

Deploying from S3 allows for larger deployment bundles, and allows you to deploy
the same bundle from different machines. Note that, although Terraform allows you
to specify a version for the S3 object, that's not supported by this module: I
believe that versioning should be incorporated in the bundle's name.

```
locals {
  lambda_name     = "example"
}


module "example_lambda" {
  source = "github.com/kdgregory/aws-misc.git//terraform/modules/lambda?ref=COMMIT"

  name          = local.lambda_name
  description   = "An example Lambda uploaded by Terraform config"

  handler       = "lambda_handler.handler"
  runtime       = "python3.8"
  s3_bucket     = "com-example-bundles"
  s3_key        = "example/1.0.0/deployment.zip"
}
```


### Deploying into a VPC

To deploy into a VPC, you must provide that VPC's ID and the IDs of one or more
subnets within the VPC. You may also provide the IDs of one or more security
groups, which will be attached to the Lambda.

Whether or not you provide a list of security groups, the module creates a new
group named after the Lambda, with an unlimited egress rule and no ingress rules.
This group is intended to be attached to some other security group, such as that
protecting an RDS database, to allow access from the Lambda.


```
locals {
  lambda_name     = "example"
}


module "example_lambda" {
  source = "github.com/kdgregory/aws-misc.git//terraform/modules/lambda?ref=COMMIT"

  name                = local.lambda_name
  description         = "An example Lambda uploaded by Terraform config"

  handler             = "lambda_handler.handler"
  runtime             = "python3.8"
  s3_bucket           = "com-example-bundles"
  s3_key              = "example/1.0.0/deployment.zip"

  vpc_id              = "vpc-12345678"
  subnet_ids          = [ "subnet-12345678", "subnet-98765432" ]
  security_group_ids  = [ "sg-12312212" ]
}
```


## Implementation Notes

### Resource Naming

  Te provided `name` parameter is used for all resources created by this module. As such,
  it must follow the strictest validation criteria for such resources. As a general rule,
  stick to US-ASCII alphanumeric characters and hyphens.

  The execution role name appends the deployment region to the Lambda name (along with the
  suffix "ExecutionRole"). This is done because role names must be unique within an account,
  while you can deploy the same Lambda into multiple regions.


### CloudWatch Log Group

  This module creates a log group, rather than allowing the Lambda to create one as needed.
  While this has the benefit of allowing you to set the retention period for log messages,
  it binds the lifetime of the group to the module: if you decide to remove the Lambda from
  your deployment, the log group and all messages that it contains will be deleted as well.

  Unfortunately, there's no way around this, lifecycle rules notwithstanding. When you remove
  part of your configuration, Terraform will delete the relevant resources.


### "Marker" Security Group

  When deployed in a VPC, this module creates a "marker" security group and assigns it to
  the Lambda. The intention of this marker group is that you can use it in an ingress
  rule for some other security group, such as that belonging to an RDS database.

  By default, the marker group is given a `Name` tag, which contains the security group
  name (this is to support displaying the group in the AWS Console). If you provide tags
  for the Lambda, and those tags include `Name`, then your provided value overrides the
  default.
