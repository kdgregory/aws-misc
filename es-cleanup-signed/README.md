# ElasticSearch Cleanup - Signed

This function deletes old ElasticSearch indexes. It is described in [this blog post](http://blog.kdgregory.com/2018/02/cleaning-up-aws-elasticsearch-indexes.html).

This variant is required when running a Lambda that lives outside the VPC against an ElasticSearch cluster
that also lives outside the VPC (which is the only type that accepts input from Kinesis Firehose). If your
VPC uses a NAT, and your ElasticSearch cluster allows IP-based access via that NAT, you may find it easier
to set up the [unsigned](../es-cleanup-unsigned) variant.


## Lambda Configuration

Runtime: Python 3.6

Required Memory: 128 MB

Timeout: 15 sec


## Environment variables

* `ELASTIC_SEARCH_HOSTNAME`: hostname of the ElasticSearch cluster
* `NUM_INDEXES_TO_KEEP`: the number of indexes to retain
* `INDEX_PREFIX`: used to identify indexes to delete (eg: "logstash-")
* IAM session identity: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_REGION`


## Permissions Required

* `AWSLambdaBasicExecutionRole`
* `es:ESHttpGet`
* `es:ESHttpDelete`


## Building the Deployment Bundle

```
pip install aws-requests-auth -t `pwd`

zip -r /tmp/escleanup.zip .
```


## Additional Information

This Lambda is designed to be triggered by a CloudWatch [scheduled event](https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/ScheduledEvents.html).
I recommend triggering during a low-use period, although the deletion operation seems to run
pretty quickly.

The ElasticSearch cluster must grant permission to the Lambda function. Assuming that your
cluster currently grants access by IP, you can add a statement like the following (changing
`ACCOUNT_ID`, `ROLE_NAME`, and `CLUSTER_NAME`):

```
{
  "Effect": "Allow",
  "Principal": {
    "AWS": "arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME"
  },
  "Action": [ "es:ESHttpGet", "es:ESHttpDelete" ],
  "Resource": "arn:aws:es:us-east-1:ACCOUNT_ID:domain/CLUSTER_NAME/*"
}
```
