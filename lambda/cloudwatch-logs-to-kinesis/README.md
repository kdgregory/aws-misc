This function is triggered by a CloudWatch Logs subscription; it writes the log events
to a named Kinesis stream so that they can be picked up by the logging pipline that I
describe [here](https://www.kdgregory.com/index.php?page=aws.loggingPipeline). It also
performs the following transformations on the events:

* If they're not already JSON, they're converted to JSON with `timestamp` and `message`
  fields. The timestamp is formatted as an ISO-8601 datetime.
* The origin log group and log stream names are added, as a child object under the key
  `cloudwatch` (this object has two fields, `logGroup` and `logStream`).
* If the message appears to be a Lambda execution report, it is parsed, and the stats
  are stored in a sub-object under the key `lambdaReport`.

## Important Caveats and Warnings

This function makes a _best-effort_ attempt to post messages to Kinesis. It retries if
messages are rejected, and will continue to do so until the Lambda timeout expires. Any
other Kinesis-related exceptions will cause the function to abort (they are all
unrecoverable, and typically caused by misconfiguration).

AWS does not document the retry policy for Cloudwatch Logs subscriptions, but if it
does retry after a failed execution, duplicate messages may be added to the stream.

Based on my experiments, Lambda will invoke the function every time a log stream
receives new messages, and each invocation covers only a single stream. In a busy
system, this could translate to many millions of invocations per month (assuming
one per second, approximately 2.6 million invocations and 33,000 GB/seconds). This
result in a monthly cost of approximately $0.50 per active stream (which in my opinion
is not onerous).


## Lambda Configuration

Runtime: Python 3.x

Required Memory: 128 MB

Timeout: 60 sec


## Environment variables

* `STREAM_NAME`: the name of the destination Kinesis stream.


## Permissions Required

* `AWSLambdaBasicExecutionRole`
* `kinesis:PutRecords`


## Deployment

If you're just trying this out, I think the easiest way to deploy it is via the Console:
it's a single Python file that can be pasted into the Lambda editor. You can also create
subscriptions directly from the CloudWatch log group.

However, for production use you should script the deployment, especially subscriptions.
Making this challenging, the script is too large to be included inline, and CloudFormation
doesn't ([yet](https://github.com/aws-cloudformation/aws-cloudformation-coverage-roadmap/issues/89))
support reading templates from arbitrary URLs. So I've included two automated approaches.

### CloudFormation

To start, you need to create a deployment bundle and copy it to S3. Replace `BUCKET`
with the name of your deployment bucket (feel free to replace `subscriber-deployment.zip`
as well):

```
zip /tmp/subscriber-deployment.zip lambda_function.py 

aws s3 cp /tmp/subscriber-deployment.zip s3://BUCKET/subscriber-deployment.zip
```

Next, create a stack from the [CloudFormation template](cloudformation.yml). I prefer to
use the AWS Console to create stacks, especially those that have multiple parameters.

This stack contains the following parameters; all except `SourceBucket` have default
values:

| Name                  | Description
|-----------------------|-------------
| `LambdaName`          | The name to use when creating the Lambda function. Will also be used as a prefix for the associated role.
| `SourceBucket`        | The name of the S3 bucket where you uploaded the deployment ZIP.
| `SourceKey`           | The key within that bucket that you used when uploading the deployment ZIP.
| `KinesisStreamName`   | The name of an existing Kinesis stream that will receive log events.
| `LogGroupName`        | The name of an existing CloudWatch log group that will be subscribed to the Lamba. Leave blank to omit the subscription.


The template specifies a single (optional) subscription, but in the real world you'll probably
want to subscribe multiple log groups. Duplicate the existing `AWS::Logs::SubscriptionFilter`
entry, giving each new entry its own logical name, and removing the `Condition` attribute. You
can also remove the `LogGroupName` parameter and related condition, as they're no longer needed.


### Serverless Application Model (SAM)

To avoid manually ZIPping and uploading the Lambda function, you can [install the SAM
cli](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html),
then execute the following commands from within the `sam` sub-directory (again, replacing
`BUCKET` with your bucket name):

```
sam build

sam package --s3-bucket BUCKET --output-template output.yaml
```

You can then use the CloudFormation console to create the stack. This variant requires the
same parameters as the CloudFormation variant, except the source bucket/key (because SAM
will fill those in automatically). 

*Note:* SAM wants the function source code to be in a `src` directory. To avoid duplication,
I've used a symlink. If you're running on Windows you will need to copy the file explicitly.
