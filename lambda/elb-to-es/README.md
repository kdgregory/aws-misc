This function parses Elastic Load Balancer log output, converts it to JSON, and uploads it to
Elasticsearch. It is triggered when the logfile is written to S3, and uses signed requests to
the Elasticsearch bulk API.


## Configuration

You can deploy the Lambda either inside or outside of a VPC. As a general rule, deploy it wherever 
you've deployed your Elasticsearch cluster. If deployed inside a VPC, it must be able to access
files stored on S3, either via NAT or VPC Gateway. 

Basic Lambda configuration:

  * Runtime: Python 3.7+
  * Required Memory: 256 MB (although 1024 will provide more CPU and handle larger files)
  * Timeout: 30 sec

IAM Permissions:

* `AWSLambdaBasicExecutionRole`/`AWSLambdaVPCAccessExecutionRole` or equivalent explicit policies.
* `es:ESHttpPost`
* `s3:GetObject`
* `s3:HeadObject`

Environment variables:

* `ELASTIC_SEARCH_HOSTNAME`: hostname of the Elasticsearch cluster (_not_ URL, which is what you
  copy from the AWS Console page).

* `ES_INDEX_PREFIX`: (optional) defines a prefix for Elasticsearch indexes created by the Lambda;
  default is "elb". If you have multiple load balancers feeding a single Elasticsearch cluster and
  want to keep their logs separate, use a separate Lambda for each with different values for this
  variable.

* `ELB_TYPE`: (optional) identifies the type of load balancer, and therefore the parser used to
  process its logfiles. The default is "ALB", for an Application load balancer. If you're using
  a Classic load balancer, change to "CLB". Other load balancer types are not currently supported.

* `BATCH_SIZE`: the number of logfile lines that will be posted to Elasticsearch as a single batch.
  The default (1000) has been shown to keep Elasticsearch happy; you may see slightly improved
  performance by increasing it.

* IAM session identity (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, and
  `AWS_REGION`): these are used to configure the `aws-requests-auth` module. They are provided
  by the Lambda runtime but must be explicitly configured if you want to run locally. If using
  long-term (user) credentials, you can omit `AWS_SESSION_TOKEN`.


## Building and Deploying

Assuming that you have `make` installed, you can use it to produce the Lambda deployment bundle
and upload it to S3:

```
make upload S3_BUCKET=com-example-deployment S3_KEY=alb-to-es.zip
```

Once uploaded, you can then deploy with the [provided CloudFormation template](cloudformation.yml).
There are several parameters that you must configure for this template. For example, using my
[cf-runner](../../utils/cf-runner.py) script:

```
cf-runner.py ALB-To-Elasticsearch \
             cloudformation.yml \
             SourceBucket=com-example-deployment \
             SourceKey=alb-to-es.zip \
             LogsBucket=com-example-logs \
             LogsPrefix=LoadBalancer/ \
             ElasticsearchHostName=search-logs-9hwrfm5ip2md537eqpt5jspqm.us-east-1.es.amazonaws.com \
             ElasticsearchArn=arn:aws:es:us-east-1:123456789012:domain/logs
```

This template creates the Lambda itself, its log group, and its execution rule. One thing that it
does _not_ do is configure the bucket to notify the Lamdba. With CloudFormation, notifications must
be configured at the time you create the bucket, and you will normally create that bucket in a base
infrastructure script.

The simplest solution to this problem is to update the Lambda's trigger in the Console.


## Additional Information

The logfile is retrieved from S3 and stored in memory for processing. If you have relatively
low traffic, or configure your load balancer to write files every 5 minutes (a good idea in
any case), 256 MB of memory should be sufficient. Look at the logged statistics to see if you
are close to that (the Lambda will abort if you need more). However, consider increasing memory
to 1024 MB for the improved CPU that comes with it.

The Lambda relies on Elasticsearch auto-creating any required indexes. The Lambda names each
index after the date of the records it contains: for example, `elb-2021-08-01`. You can
configure the prefix (here "elb") using the `ES_INDEX_PREFIX` environment variable. For a low
volume server, you might prefer to use one index per month. If so, you'll need to change the
`process_record()` method: replace the `[0:10]` substring operation with `[0:7]`.
