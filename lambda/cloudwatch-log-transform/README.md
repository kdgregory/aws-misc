This function is part of a pipeline that copies events from CloudWatch Logs into
Elasticsearch. The entire pipeline consists of the following stages:

1. An application (typically a Lambda function) writes events to CloudWatch Logs.
2. A subscription on the log group copies records into a Kinesis stream.
3. This function reads the records from the source Kinesis stream, transforms them
   if necessary, and writes them to another Kinesis stream.
4. Kinesis Firehose reads events from this second stream and writes them to
   Elasticsearch.

As part of step 3, this function performs the following transformations on the source
records:

* If they're not already JSON, they're converted to JSON with `timestamp`, `message`,
  and `level` fields. The timestamp is formatted as an ISO-8601 datetime, and the
  level is always `INFO`.
* The origin log group and log stream names are added, as a child object under the key
  `cloudwatch` (this object has two fields, `logGroup` and `logStream`).
* If the message appears to be a Lambda execution report, it is parsed, and the stats
  are stored in a sub-object under the key `lambda`.
* If the message appears to by output from the Python logger, it is parsed, the original
  timestamp and logged message are extracted, and the Lambda request ID is stored in a
  child object under the key `lambda`.

## Warnings and Caveats

This function makes a _best-effort_ attempt to post messages to the destination stream:
it will retry any individual messages that are rejected by the destination stream
(typically due to throttling at the shard level), until the Lambda times out. Messages that
are rejected due to "internal error" are logged and dropped. Any other exception causes the
function to abort (they typically indicate misconfiguration, and are unrecoverable).

You may also find duplicate messages: the Kinesis trigger will retry on any failed send.
If this is due to persistent throttling, then the messages that _were_ successfully sent
in a prior batch will be resent.


## Lambda Configuration

Runtime: Python 3.x

Required Memory: 128 MB

Recommended Timeout: 60 sec


### Environment variables

* `DESTINATION_STREAM_NAME`: the name of the Kinesis stream where messages will be written.


### Permissions Required

* `AWSLambdaBasicExecutionRole`
* Source stream: `kinesis:DescribeStream`, `kinesis:GetRecords`, `kinesis:GetShardIterator`,
  `kinesis:ListStreams`
* Destination stream: `kinesis:PutRecords`


## Deployment

Deploying this function is a multi-step process, so I've created CloudFormation templates
to help. I've also created a Serverless Application Model (SAM) template for the Lambda
function.

### Subscription Stream 

> Note: I assume that you already have a logging pipeline with destination stream, Firehose,
  and Elasticsearch. If not, you can find CloudFormation templates to set up a pipeline
  [here](https://github.com/kdgregory/log4j-aws-appenders/tree/master/examples/cloudformation).

The Kinesis stream and CloudWatch subscription are created as two separate steps: the
subscription can't be created until the stream has become active, and CloudFormation
doesn't support tracking of resources (other than wait conditions, which require manual
intervention).

* The [Kinesis](cloudformation/kinesis.yml) template creates a single-shard Kinesis
  stream and the IAM role that allows CloudWatch to write to that stream. The stream
  name is specified via the `StreamName` parameter.

* The [Subscription](cloudformation/subscription.yml) template subscribes a single
  log group, specified with the `LogGroupName` parameter, to the Kinesis stream
  specified with the `StreamName` parameter (the default values for this parameter
  are the same in both templates).

  For actual use, you'll probably create multiple subscriptions; all can go to the
  same stream (although you might need to increase the shard count to handle load).
  In that case, simply replicate the subscription resource (giving each a unique
  name), and hardcode the log group name rather than using a parameter.

### Lambda (CloudFormation)

The [Lambda](cloudformation/lambda.yml) template creates the Lambda function to
transform log events and write them to Kinesis, the execution role that lets it
do its job, and an event source that attaches it to the Kinesis stream created
above. It uses for following parameters to control its operation:

* `LambdaName`: The name of the function to create (default: `CloudWatchLogsTransformer`)
* `SourceBucket: The S3 bucket where the deployment bundle can be found (see below).
* `SourceKey: The path in that bucket for the deployment bundle (see below).
* `SourceStreamName: The Kinesis stream that contains CloudWatch Logs events (which
  you created above).
* `DestinationStreamName: The Kinesis stream for transformed log messages (which you
  created previously).

CloudFormation requires you to provide a deployment bundle for a Lambda function, even
when it's just a single file. So, from the project directory, execute the following
commands, replacing `YOUR_BUCKET_NAME` with an existing bucket that belongs to you:

```
zip /tmp/cloudwatch_logs_transformer.zip lambda_function.py 

aws s3 cp /tmp/cloudwatch_logs_transformer.zip s3://YOUR_BUCKET_NAME/cloudwatch_logs_transformer.zip
```

The event source mapping is hardcoded to start reading from the end of the stream,
with a maximum batch size of 100 records and a maximum delay of 30 seconds.


### Serverless Application Model (SAM)

To avoid manually ZIPping and uploading the Lambda function, you can [install the SAM
cli](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html),
then execute the following commands from within the `sam` sub-directory (again, replacing
`YOUR_BUCKET_NAME` with your actual bucket name):

```
cd sam

sam build

sam package --s3-bucket YOUR_BUCKET_NAME --output-template output.yaml
```

You can then use the CloudFormation console to create the stack. This variant requires the
same parameters as the CloudFormation variant, except the source bucket/key (because SAM
will fill those in automatically). 

*Note:* SAM wants the function source code to be in a `src` directory. To avoid duplication,
I've used a symlink. If you're running on Windows you will need to copy the file explicitly.
