# CloudWatch Logs Cleanup

A Lambda function to delete CloudWatch log streams that have exceeded their group's
retention period. This is needed because CloudWatch will delete the messages but
not the streams; in an environment that creates lots of streams (like Lambda), you
will end up with lots of empty streams. While these may or may not affect the
performance of CloudWatch Logs operations such as Insights, it's confusing to see
them all in the Console.


## Configuration

Basic Lambda configuration:

  * Runtime: Python 3.7+
  * Required Memory: 256 MB
  * Timeout: 60 seconds (increase if you have lots of log groups/streams)

IAM Permissions:

* `AWSLambdaBasicExecutionRole`/`AWSLambdaVPCAccessExecutionRole` or equivalent explicit policies.
* `logs:DeleteLogStream`
* `logs:DescribeLogGroups`
* `logs:DescribeLogStreams`
* `logs:GetLogEvents`

Trigger via EventBridge schedule.


## Building and Deploying

The easiest way to build and deploy this Lambda is with `make`. The provided Makefile has three
relevant targets:

* `build`: builds the deployment bundle (`logs_cleanup.zip`) and stores it in the project directory.
  You would normally invoke this target only if you're making changes and want to upload manually.

* `upload`: builds the deployment bundle and then uploads it to an S3 bucket. You must provide
  the name of the bucket when invoking this target; you can optionally give the bundle a different
  name:

  ```
  # option 1, use predefined key
  make upload S3_BUCKET=my_deployment_bucket

  # option 2, use explicit key
  make upload S3_BUCKET=my_deployment_bucket S3_KEY=my_bundle_name.zip
  ```

* `deploy`: builds the deployment bundle, uploads it to S3, and then creates a CloudFormation
  stack that creates the Lambda and all related resources (by default named `CloudWatchLogsCleaner`,
  which is also the name of the created Lamdba).

  ```
  # option 1: use defaults
  make deploy S3_BUCKET=my_deployment_bucket

  # option 2: configure what you can
  make deploy STACK_NAME=CloudWatchCleaner S3_BUCKET=my_deployment_bucket S3_KEY=my_bundle_name.zip TIMEOUT=900
  ```


## Usage Notes

### Large numbers of log groups/streams

If you have a large number of groups or streams, this Lambda might not be able to
examine all of them before timing out. To work around this problem, it does two
things:

* First, itt uses an an environment variable, `MAX_LOG_GROUPS`, to limit the number
  of log groups it will examine per invocation.

  It not set, this value defaults to 1,000,000, which is the [documented
  quota](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/cloudwatch_limits_cwl.html)
  for log groups per account and region. If you have anywhere near this number of
  groups, then a Lambda is the wrong solution to the problem.

  The CloudFormation script defaults this value to 60, with a Lambda timeout of 180
  seconds. This ration is based on my experience; if you have a large number of
  streams per group, you may need to either reduce the number of groups examined
  or increase the Lambda timeout.

* The second thing that the Lambda does is to shuffle log groups before processing
  them. This ensures that, even if the Lambda does not run long enough to examine
  all groups, multiple runs should cover everything.

Another issue with large numbers of groups and streams is that the API calls are
throttled at a relatively low rate: `DescribeLogGroups` and `DescribeLogStreams`
default to 5 calls per second (these can be increased), while `GetLogEvents`
is limited to 10 (which can't be increased). There's no documented quota for
`DeleteLogStream`.

To avoid throttling, which can impact other applications, this Lambda uses sleeps to
rate-limit its calls. It's also resilient to throttling exceptions: any exceptions
are trapped at the group level, so subsequent groups will continue processing.

Finally, if you have a large number of groups/streams, you should schedule the
Lambda to run more frequently than once a day. Start with every hour and see how
long it takes to run.
