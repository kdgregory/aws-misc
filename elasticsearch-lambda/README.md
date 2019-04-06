These are some lambdas that I describe in [this article](https://www.kdgregory.com/index.php?page=aws.loggingPipeline).

| Directory                                 | Contents
|-------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------
[cli](cli)                                  | A collection of bash snippets using the AWS CLI
[elb-to-es](elb-to-es)                      | A Lambda to import Elastic Load Balancer logfiles into Elasticsearch.
[es-cleanup-signed](es-cleanup-signed)      | A Lambda to clean up old indexes from an Elasticsearch cluster. See [this](https://www.kdgregory.com/index.php?page=aws.loggingPipeline) for more info.
[es-cleanup-unsigned](es-cleanup-unsigned)  | A cleanup Lambda for Elasticsearch clusters that allow unsigned access.
