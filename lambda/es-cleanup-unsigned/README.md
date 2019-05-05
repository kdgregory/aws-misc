# ElasticSearch Cleanup - Unsigned

This function deletes old ElasticSearch indexes. It is described in [this blog post](http://blog.kdgregory.com/2018/02/cleaning-up-aws-elasticsearch-indexes.html).

This variant uses unsigned HTTP requests. It is appropriate when you can run inside the VPC and use
either IP-based or security-group-based access to your ElasticSearch cluster. If you need to make
signed requests, see [es-cleanup-signed](../es-cleanup-signed).


## Lambda Configuration

Runtime: Python 3.6

Required Memory: 128 MB

Timeout: 15 sec


## Environment variables

* `ELASTIC_SEARCH_HOSTNAME`: hostname of the ElasticSearch cluster
* `NUM_INDEXES_TO_KEEP`: the number of indexes to retain
* `INDEX_PREFIX`: used to identify indexes to delete (eg: "logstash-")


## Permissions Required

* `AWSLambdaBasicExecutionRole`


## Building the Deployment Bundle

Not necessary: this is a single-file deployment.


## Additional Information

This Lambda is designed to be triggered by a CloudWatch [scheduled event](https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/ScheduledEvents.html).
I recommend triggering during a low-use period, although the deletion operation seems to run
pretty quickly.
