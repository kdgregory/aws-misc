**This sub-project is obsolete.** Instead, use the transformation based on Eventbridge
Pipes [here](../cloudwatch-log-transform-2).

----

This Lambda decomposes messages that have been written to a Kinesis stream by a CloudWatch
Logs subscription, writing them to a destination stream as individual log events. See [this
blog post](https://blog.kdgregory.com/2019/09/streaming-cloudwatch-logs-to.html) for more
information about why this is necessary.

The specific transformations are:

* Multiple log events are broken out of the source Kinesis record and written as distinct
  records on the destination stream.
* If a log event is not JSON, it is transformed into a JSON object containing the fields
  `timestamp`, `message`, and `level`. The timestamp is the log event timestamp reported
  by CloudWatch, and is formatted as an ISO-8601 datetime (eg, "2021-08-23-11:15:12Z").
  The level is always `INFO`.
* If the log event is already JSON, it is examined and a `timestamp` field added if one
  doesn't already exist, using the value/format above.
* The origin log group and log stream names are added, as a child object under the key
  `source`. This object has two fields, `logGroup` and `logStream`.
* If the message appears to be a Lambda execution report, it is parsed, and the stats
  are stored in a sub-object under the key `lambda`.
* If the message appears to be output from the [Lambda Python logging
  library](https://docs.aws.amazon.com/lambda/latest/dg/python-logging.html#python-logging-lib),
  it is parsed, the original timestamp and logged message are extracted, and the Lambda
  request ID is stored in a child object under the key `lambda`.

Warnings and Caveats

* All CloudWatch log groups must be subscribed to a _single_ Kinesis stream, which is then
  processed by this Lambda and written to a _single_ Kinesis destination stream.

* This function makes a _best-effort_ attempt to post messages to the destination stream:
  it will retry any individual messages that are rejected by the destination stream
  (typically due to throttling at the shard level), until the Lambda times out. Messages that
  are rejected due to "internal error" are logged and dropped. Any other exception causes the
  function to abort (they typically indicate misconfiguration, and are unrecoverable).

* You may also find duplicate messages: the Kinesis trigger will retry on any failed send.
  If this is due to persistent throttling, then the messages that _were_ successfully sent
  in a prior batch will be resent.


## Lambda Configuration

General:

* Runtime: Python 3.7+
* Recommended Memory: 512 MB (for CPU; actual memory requirement is much lower)
* Recommended Timeout: 30 seconds


Environment variables

* `DESTINATION_STREAM_NAME`: the name of the Kinesis stream where messages will be written.


Permissions Required

* `AWSLambdaBasicExecutionRole`
* Source stream: `kinesis:DescribeStream`, `kinesis:GetRecords`, `kinesis:GetShardIterator`,
  `kinesis:ListStreams`
* Destination stream: `kinesis:PutRecords`


## Building and Deploying

*Note:* The source and destination Kinesis streams must exist before deploying this Lambda.

The easiest way to build and deploy is with `make`. The provided Makefile has three targets
for the Lambda:

* `build`: builds the deployment bundle (`log_transform.zip`) and stores it in the project directory.
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
  stack (by default named `LogsTransformer`, which is also the name of the created Lamdba)
  that creates the Lambda and all related resources. You must provide the names of the Kinesis
  streams, and may override the stack (Lambda) name.

  ```
  # option 1: use defaults
  make deploy S3_BUCKET=my_deployment_bucket SOURCE_STREAM=subscription_dest DEST_STREAM=log_aggregator

  # option 2: specify stack name and deployment bundle
  make deploy STACK_NAME=CloudWatchSubscriptionTransformer S3_BUCKET=my_deployment_bucket S3_KEY=my_bundle_name.zip SOURCE_STREAM=subscription_dest DEST_STREAM=log_aggregator
  ```

In addition to creating all resources for the Lambda, this stack also creates a role that allows
CloudWatch logs to write to the Kinesis stream. This role has the name `STACKNAME-SubscriptionRole`.

Finally, the Makefile also provides a target to subscribe a CloudWatch log group to a Kinesis
stream, using information from the created stack:

```
# option 1: use the default stack name
make subscribe LOG_GROUP=my_logs

# option 2: use a custom stack name
make subscribe STACK_NAME=CloudWatchSubscriptionTransformer LOG_GROUP=my_logs
```

This last target implemented using the AWS CLI, not CloudFormation. You can subscribe as many
log groups as you'd like to a single Kinesis stream, but must use the Console to remove the
subscription.
