Manages a Lambda deployment bundle in S3.

Deploying a Lambda from an S3 bundle can be a challenge. If the bundle already
exists when you first deploy the Lambda, everything is easy. But updating and
redeploying can be a challenge, since updating the S3 object will not trigger
a Lambda update. And in some cases, you may not want to update the Lambda even
if you've built a new deployment bundle (eg, if you use the same source tree for
multiple Lambdas).

This module is an attempt to provide a flexible deployment mechanism using S3:

* If there is no object on S3, it can upload a local file.
* It can determine whether or not to replace an existing S3 file with a new build.
* It can reference an existing S3 file for deployments that happen outside of builds.


## Configuration

You must enable versioning on the deployment bucket in order to trigger updating
a Lambda from a deployment bundle.

You can then provide the following variables to this module:

* `s3_bucket`

  The bucket where the deployment bundle is/should be stored. Note that this
  must reside in the same region as your Lambda function.

  Default: none; you must specify this

* `s3_key`

  The Amazon S3 key of the deployment package.

  Default: none; you must specify this

* `filename`

  The name of a local file containing the deployment bundle. If you omit this,
  and the bundle does not already exist on S3, apply will fail.

  Default: null

* `overwrite_if_updated`

  If `true`, updating the local file will update the S3 object and redeploy the Lambda.
  If `false`, changes to the local file are ignored.

  This is typically set by some other variable in the configuration. For example, you
  may want to update a development Lambda every time it changes, but not update the
  production Lambda unless some other condition is true. In that case, you would create
  an expression that captured these two conditions, and pass that to the module.

  Default: false


## Outputs

* `s3_bucket`

  The bucket name, taken from the like-named attribute of the `aws_s3_object`. Pass
  this to the Lambda configuration to ensure that updates are propagated.

* `s3_key`

  The deployment package key, taken from the like-named attribute of the `aws_s3_object`.
  Pass this to the Lambda configuration to ensure that updates are propagated.

* `s3_version`

  The version of the object on S3, if it is stored in a versioned bucket (null otherwise).


## Example

Update `COMMIT` to an appropriate hash. Do not use `trunk` unless you're OK with deployment
configs that may change outside of your control.

```
module "deployment_bundle" {
  source = "github.com/kdgregory/aws-misc.git//terraform/modules/s3_deployment?ref=COMMIT"

  s3_bucket             = "com-example-deployment"
  s3_key                = "example/example.zip"
  filename              = local.filename
  overwrite_if_updated  = false
}


module "lambda" {
  source = "github.com/kdgregory/aws-misc.git//terraform/modules/lambda?ref=COMMIT"

  name                  = local.lambda_name
  description           = "An example Lambda uploaded by Terraform config"

  runtime               = "python3.8"
  handler               = "lambda_handler.handler"

  s3_bucket             = module.deployment_bundle.s3_bucket
  s3_key                = module.deployment_bundle.s3_key
  s3_version            = module.deployment_bundle.s3_version
}
```
