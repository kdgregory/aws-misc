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

This is a single Lambda function, using only standard libraries; it can be installed
via copy-paste into the AWS Console. 

You can also add subscriptions via the AWS Console: select a log group, choose the
&ldquo;Stream to AWS Lambda&rdquo; action, and follow the prompts. Multiple log groups
can be streamed to a single Lambda.

The destination Kinesis stream must already exist.
