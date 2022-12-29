This Lambda is called as from an EventBridge pipeline to extract individual log events
from a CloudWatch Logs subscription message. The specific transformations are:

* Each log event is returned as a separate record.
* If a log event is not JSON, it is transformed into a JSON object containing the
  fields `timestamp` and `message`. The timestamp is the log event timestamp reported
  by CloudWatch, and is formatted as an ISO-8601 datetime (eg, "2021-08-23-11:15:12Z").
* Once the log event is JSON, a child record is added with the key `cloudwatch`. This
  record contains the log group and log stream names, as well as the timestamp returned
  by CloudWatch.

## Deployment

I've provided a CloudFormation template, [pipeline.yml](./pipeline.yml), that creates the
two Kinesis streams, the EventBridge pipeline, the transformation Lambda, and associated
IAM roles. This template includes the entire source for the Lambda function, so there is
no need to separately deploy (unless you add functionality).

> **Beware:** if you deploy this template, you will be charged for the Kinesis streams
  that it creates.

Using my [cf-deploy](https://github.com/kdgregory/aws-misc/blob/trunk/utils/cf-deploy.py)
script:

```
cf-deploy.py LogsTransformPipeline pipeline.yml
```

The template lets you configure the pipeline batch size, using the `BatchSize` parameter.
The default is 1, meaning that the pipeline invokes the transformer for each record it
reads off the subscription stream. You should increase this for production use to 100 or
perhaps more (you may need to increase Lambda memory to support large batches). You can
also adjust the time that EventBridge waits to fill a batch, with the `BatchWindowSeconds`
parameter; the default of 30 gives you relatively fast response times, at the penalty of
perhaps not filling a batch.

The stack outputs the ARNs for source and destination streams. You'll need the source
stream ARN to subscribe to a CloudWatch log group, and can retrieve it using my
[cf-env](https://github.com/kdgregory/aws-misc/blob/trunk/utils/cf-env.py) script (this
sets an environment variable that will be used in the next step):

```
$(cf-env.py LogsTransformPipeline SUBSCRIPTION_STREAM=SourceStreamArn)
```


## Stream Subscription

The CloudFormation template [subscription.yml](./subscription.yml) creates a single 
subscription, along with an IAM role that can be used for all subscriptions. To deploy
it for the log group `AppenderExample` (which must already exist) and the Kinesis stream
created in the previous step:

```
cf-deploy.py LogsSubscription subscription.yml StreamArn=${SUBSCRIPTION_STREAM} LogGroupName=AppenderExample
```

You need to create one `AWS::Logs::SubscriptionFilter` for each of the log groups that
you want to use. With CloudFormation, the best way to do this is to use a
[module](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/modules.html)
to create your log groups, and let it create subscriptions at the same time.
Unfortunately, this is hard to retrofit if you already have logs, so the easiest
solution is to maintain a template of subscriptions with hardcoded stream names.


## Seeing it in action

If you want to generate some log events, you can use [one of the examples for my appender
library](https://github.com/kdgregory/log4j-aws-appenders/tree/trunk/examples/log4j1-example),
with this `src/main/resources/log4j.properties`:

```
log4j.rootLogger=WARN, console, cloudwatch

log4j.logger.com.kdgregory=DEBUG

log4j.appender.console=org.apache.log4j.ConsoleAppender
log4j.appender.console.layout=org.apache.log4j.PatternLayout
log4j.appender.console.layout.ConversionPattern=%d{ISO8601} %-5p [%t] %c - %m%n

log4j.appender.cloudwatch=com.kdgregory.log4j.aws.CloudWatchAppender
log4j.appender.cloudwatch.logGroup=AppenderExample
log4j.appender.cloudwatch.logStream=Log4J1-Example-{date}-{hostname}-{pid}
log4j.appender.cloudwatch.layout=com.kdgregory.log4j.aws.JsonLayout
log4j.appender.cloudwatch.layout.appendNewlines=true
log4j.appender.cloudwatch.layout.enableHostname=true
log4j.appender.cloudwatch.layout.enableLocation=true
log4j.appender.cloudwatch.layout.enableInstanceId=false
log4j.appender.cloudwatch.layout.enableAccountId=true
```

Then, open up three windows. You'll run the logging example in the first (instructions for
building and running can be found at the link above). In the second, you'll use my
[kinesis_reader](https://github.com/kdgregory/aws-misc/blob/trunk/utils/kinesis_reader.py)
script to read the messages produced by the subscription filter:

```
kinesis_reader.py log-subscription
```

And in the third, you'll read the events produced by the pipeline:

```
kinesis_reader.py log-records
```

Note that it will take a few moments from the time you start writing events to the time they
appear in the third window.


## Next Steps

The reason for creating this pipeline is to decompose events so that they can be written to
an Elasticsearch server by way of a Kinesis Firehose. You'll find [CloudFormation templates
to create those services](https://github.com/kdgregory/log4j-aws-appenders/tree/trunk/examples/cloudformation)
in my logging library.

You might also want to enhance the transformation Lambda. In order to minimize the size of
the CloudFormation template, I removed some functionality from my [previous
iteration](../cloudwatch-log-transform).  In particular, this new version doesn't try to
parse Lamba execution reports.
