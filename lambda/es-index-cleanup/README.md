# ElasticSearch Cleanup

This function deletes old ElasticSearch indexes, as described in [this blog
post](http://blog.kdgregory.com/2018/02/cleaning-up-aws-elasticsearch-indexes.html).

It is intended for older versions of Amazon's managed Elasticsearch service, which
did not provide any way to manage indexes. Recent versions support [Index State
Management](https://docs.aws.amazon.com/elasticsearch-service/latest/developerguide/ism.html),
which allows extensive control of indexes.

This Lambda is designed to be triggered by a CloudWatch [scheduled event](https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/ScheduledEvents.html).
I recommend triggering during a low-use period, although the deletion operation seems to run
pretty quickly.


## Lambda Configuration

Runtime: Python 3.6+

Required Memory: 256 MB

Timeout: 15 sec

Environment variables:

* `ELASTIC_SEARCH_HOSTNAME`: hostname of the ElasticSearch cluster
* `NUM_INDEXES_TO_KEEP`: the number of indexes to retain
* `INDEX_PREFIX`: used to identify indexes to delete (eg: "logstash-")
* IAM session identity (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, and
  `AWS_REGION`): these are used to configure the `aws-requests-auth` module. They are provided
  by the Lambda runtime but must be explicitly configured if you want to run locally. If using
  long-term (user) credentials, you can omit `AWS_SESSION_TOKEN`.

Permissions:

* `AWSLambdaBasicExecutionRole`
* `es:ESHttpGet`
* `es:ESHttpDelete`

Third-party Modules:

* [requests](https://pypi.org/project/requests/)
* [aws-requests-auth](https://pypi.org/project/aws-requests-auth/)


## Building and Deploying

The easiest way to build and deploy this Lambda is with `make`. The provided Makefile has three
relevant targets:

* `build`: builds the deployment bundle (`elasticsearch_index_cleanup.zip`) and stores it in the
  project directory. You would normally run this directly only if you're making changes and want
  to upload manually.

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
  stack (named `ElasticsearchIndexCleanup`, which is also the name of the created Lamdba) that
  creates the Lambda and all related resources. You must provide basic connectivity information,
  and may override the stack (Lambda) name, configured index pattern and number of indexes to keep.

  ```
  # option 1: use defaults
  make deploy S3_BUCKET=my_deployment_bucket ES_HOSTNAME=search-example-3hpfi5df2mw5m7trqp5qjmespm.us-east-1.es.amazonaws.com ES_ARN=arn:aws:es:us-east-1:123456789012:domain/example

  # option 2: specify everything
  make deploy STACK_NAME=MyElasticsearchCleaner S3_BUCKET=my_deployment_bucket S3_KEY=my_bundle_name.zip ES_HOSTNAME=search-example-3hpfi5df2mw5m7trqp5qjmespm.us-east-1.es.amazonaws.com ES_ARN=arn:aws:es:us-east-1:123456789012:domain/example INDEX_PREFIX=elb- INDEX_COUNT=7
  ```

The one thing that you can't change via the Makefile is the invocation schedule. To do that, you'll
need to either edit the [template](cloudformation.yml), deploy it manually, or edit after deployed.
