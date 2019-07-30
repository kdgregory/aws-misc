Utility Lambdas.

Directory                                                   | Contents
------------------------------------------------------------|----------
[cloudwatch-log-cleanup](cloudwatch-log-cleanup)            | Deletes CloudWatch log streams that are empty because of the log group's retention period.
[cloudwatch-logs-to-kinesis](cloudwatch-logs-to-kinesis)    | Destination for a CloudWatch Logs subscription that transforms messages to JSON and puts them on a Kinesis stream.
[elb-to-es](elb-to-es)                                      | Imports Elastic Load Balancer logfiles into Elasticsearch.
[es-cleanup-signed](es-cleanup-signed)                      | Cleans up old indexes from an Elasticsearch cluster. See [this](https://www.kdgregory.com/index.php?page=aws.loggingPipeline) for more info.
[es-cleanup-unsigned](es-cleanup-unsigned)                  | An Elasticsearch cleanup Lambda for clusters that allow unsigned access.
