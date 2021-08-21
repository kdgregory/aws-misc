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

The easiest way to build and deploy this Lambda is with `make`. The provided Makefile has three
relevant targets:

* `build`: builds the deployment bundle (`elb-to-es.zip`) and stores it in the project directory.
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
  stack (by default named `ELB-Elasticsearch-Upload`, which is also the name of the created
  Lamdba) that creates the Lambda and all related resources. You must provide basic connectivity
  information, and may override the stack (Lambda) name and configured index pattern.

  ```
  # option 1: use defaults
  make deploy S3_BUCKET=my_deployment_bucket LOGS_BUCKET=my_logging_bucket LOGS_PREFIX=LoadBalancer/ ES_HOSTNAME=search-example-3hpfi5df2mw5m7trqp5qjmespm.us-east-1.es.amazonaws.com ES_ARN=arn:aws:es:us-east-1:123456789012:domain/example

  # option 2: specify everything
  make deploy STACK_NAME=LoadBalancerLogShuffler S3_BUCKET=my_deployment_bucket S3_KEY=my_bundle_name.zip LOGS_BUCKET=my_logging_bucket LOGS_PREFIX=LoadBalancer/ ES_HOSTNAME=search-example-3hpfi5df2mw5m7trqp5qjmespm.us-east-1.es.amazonaws.com ES_ARN=arn:aws:es:us-east-1:123456789012:domain/example INDEX_PREFIX=elb-
  ```

One thing that this deployment process does _not_ do is configure the bucket to notify the Lamdba.
With CloudFormation, notifications must be configured at the time you create the bucket, and you
will normally create that bucket in a base infrastructure script.

The simplest solution to this problem is to update the Lambda's trigger in the Console.


## Additional Information

The logfile is retrieved from S3 and stored in memory for processing. If you have relatively
low traffic, or configure your load balancer to write files every 5 minutes (a good idea in
any case), 256 MB of memory should be sufficient. Look at the logged statistics to see if you
are close to that (the Lambda will abort if you need more). However, consider increasing memory
to 1024 MB for the improved CPU that comes with it.

The Lambda uses a regular expression to parse log lines, and there are some log lines that it 
can't parse (typically crafted by hackers to break web servers). In this case, the Lambda skips
the unparseable line and logs an error that shows the line's content.

The Lambda relies on Elasticsearch auto-creating any required indexes. The Lambda names each
index after the date of the records it contains: for example, `elb-2021-08-01`. You can
configure the prefix (here "elb") using the `ES_INDEX_PREFIX` environment variable. For a low
volume server, you might prefer to use one index per month. If so, you'll need to change the
`process_record()` method: replace the `[0:10]` substring operation with `[0:7]`.
